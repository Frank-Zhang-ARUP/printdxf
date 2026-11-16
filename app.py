import io
import os
import re
import tempfile
import zipfile
from pathlib import Path

import streamlit as st
import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.config import Configuration, ColorPolicy, LineweightPolicy
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from pypdf import PdfReader, PdfWriter

st.set_page_config(page_title="DXF Batch to A3 PDF", page_icon="📐", layout="wide")
st.title("DXF Batch to A3 PDF")
st.caption("批量将格式一致的 DXF 平面图输出为矢量 A3 PDF，可下载单张 PDF、合并 PDF 和 ZIP。")

A3_INCH = (16.5354, 11.6929)  # 420 x 297 mm


def safe_stem(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r'[<>:"/\\|?*]+', '_', stem).strip(' .')
    return stem or 'drawing'


def unique_name(name: str, used: set) -> str:
    stem = safe_stem(name)
    candidate = stem
    i = 2
    while candidate.lower() in used:
        candidate = f"{stem}_{i}"
        i += 1
    used.add(candidate.lower())
    return candidate


def page_size(orientation: str):
    return A3_INCH if orientation == "横向" else A3_INCH[::-1]



def setup_cjk_font(doc, uploaded_font_path=None):
    """Make DXF TEXT/MTEXT/ATTRIB visible when original SHX/CJK fonts are unavailable."""
    candidates = []
    if uploaded_font_path and Path(uploaded_font_path).exists():
        candidates.append(str(uploaded_font_path))
    # Common paths/names on Streamlit Cloud/Linux and Windows/local runs.
    candidates += [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    font_path = next((x for x in candidates if Path(x).exists()), None)
    if not font_path:
        # Last resort: pick an installed font that supports broad Unicode if present.
        for f in fm.findSystemFonts():
            low = f.lower()
            if any(k in low for k in ["notosanscjk", "noto", "wenquanyi", "yahei", "simhei", "simsun"]):
                font_path = f
                break
    if not font_path:
        return None

    # ezdxf uses the font assigned to DXF text styles. Replace missing SHX/TTF
    # styles with the selected CJK font while preserving style names, height,
    # width factor, rotation and entity alignment.
    for style in doc.styles:
        try:
            style.dxf.font = font_path
            if hasattr(style.dxf, "bigfont"):
                style.dxf.bigfont = ""
        except Exception:
            pass
    return font_path


def convert_dxf_to_pdf(data: bytes, filename: str, settings: dict) -> bytes:
    with tempfile.TemporaryDirectory() as td:
        dxf_path = Path(td) / Path(filename).name
        pdf_path = Path(td) / f"{safe_stem(filename)}.pdf"
        dxf_path.write_bytes(data)

        # recover() is more tolerant of minor DXF defects than readfile().
        try:
            doc, auditor = ezdxf.recover.readfile(str(dxf_path))
        except Exception:
            doc = ezdxf.readfile(str(dxf_path))
            auditor = None

        font_path = setup_cjk_font(doc, settings.get('font_path'))
        msp = doc.modelspace()
        fig = plt.figure(figsize=page_size(settings['orientation']))
        ax = fig.add_axes([0, 0, 1, 1])

        if settings['background'] == '白色':
            bg = '#FFFFFF'
            fg_policy = ColorPolicy.BLACK
        else:
            bg = '#000000'
            fg_policy = ColorPolicy.WHITE
        fig.patch.set_facecolor(bg)
        ax.set_facecolor(bg)

        ctx = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        config = Configuration(
            color_policy=fg_policy,
            lineweight_policy=LineweightPolicy.ABSOLUTE,
            min_lineweight=settings['min_lineweight_mm'],
        )
        Frontend(ctx, backend, config=config).draw_layout(msp, finalize=True)

        ax.set_aspect('equal', adjustable='datalim')
        ax.margins(settings['margin_ratio'])
        ax.set_axis_off()

        # PDF page is exactly A3. bbox_inches is intentionally not used,
        # otherwise Matplotlib may crop the physical page below A3.
        fig.savefig(
            pdf_path,
            format='pdf',
            dpi=settings['dpi'],
            facecolor=fig.get_facecolor(),
            edgecolor='none',
            metadata={'Title': safe_stem(filename), 'Creator': 'DXF Batch to A3 PDF'},
        )
        plt.close(fig)
        return pdf_path.read_bytes()


def merge_pdfs(items):
    writer = PdfWriter()
    for _, pdf_bytes in items:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def make_zip(items):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, pdf_bytes in items:
            zf.writestr(name, pdf_bytes)
    return out.getvalue()


with st.sidebar:
    st.header("输出设置")
    orientation = st.radio("A3方向", ["横向", "竖向"], horizontal=True)
    background = st.radio("背景", ["白色", "黑色"], horizontal=True)
    margin_percent = st.slider("图纸留白", 0, 15, 3, 1, help="按绘图范围比例增加留白。")
    min_lineweight_mm = st.slider("最小线宽 (mm)", 0.05, 0.50, 0.13, 0.01)
    dpi = st.select_slider("PDF渲染 DPI", options=[150, 200, 300, 400, 600], value=300,
                           help="PDF主体为矢量；DPI主要影响图内栅格图像。")
    st.info("页面固定为 ISO A3：420 × 297 mm。程序会为 TEXT / MTEXT / ATTRIB 自动使用可用中文字体替代缺失的 SHX 字体。")

font_upload = st.file_uploader("可选：上传中文 TTF/OTF/TTC 字体", type=['ttf','otf','ttc'], accept_multiple_files=False, help="如果 DXF 使用 SHX 或特殊中文字体，建议上传 Noto Sans CJK SC、微软雅黑或黑体字体。")

uploaded = st.file_uploader(
    "上传 DXF 文件（可多选）",
    type=['dxf'],
    accept_multiple_files=True,
    help="建议先在 CAD 中执行 AUDIT/PURGE，并将所需图形放在 Model Space。",
)

if uploaded:
    st.write(f"已选择 **{len(uploaded)}** 个 DXF 文件")
    with st.expander("文件清单", expanded=False):
        for f in uploaded:
            st.write(f"• {f.name}  ({len(f.getvalue()) / 1024:.1f} KB)")

    if st.button("开始批量转换", type="primary", use_container_width=True):
        custom_font_path = None
        if font_upload is not None:
            suffix = Path(font_upload.name).suffix.lower()
            custom_font_path = str(Path(tempfile.gettempdir()) / ('uploaded_cjk_font' + suffix))
            Path(custom_font_path).write_bytes(font_upload.getvalue())

        settings = {
            'orientation': orientation,
            'background': background,
            'margin_ratio': margin_percent / 100.0,
            'min_lineweight_mm': min_lineweight_mm,
            'dpi': dpi,
            'font_path': custom_font_path,
        }
        results, errors, used = [], [], set()
        progress = st.progress(0, text="准备转换…")
        for idx, f in enumerate(uploaded, start=1):
            progress.progress((idx - 1) / len(uploaded), text=f"正在转换：{f.name}")
            try:
                stem = unique_name(f.name, used)
                pdf = convert_dxf_to_pdf(f.getvalue(), f.name, settings)
                results.append((f"{stem}_A3.pdf", pdf))
            except Exception as exc:
                errors.append((f.name, str(exc)))
            progress.progress(idx / len(uploaded), text=f"已处理 {idx}/{len(uploaded)}")

        st.session_state['pdf_results'] = results
        st.session_state['pdf_errors'] = errors
        progress.empty()

results = st.session_state.get('pdf_results', [])
errors = st.session_state.get('pdf_errors', [])

if results:
    st.success(f"转换完成：成功 {len(results)} 个，失败 {len(errors)} 个。")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "下载全部单张 PDF（ZIP）",
            data=make_zip(results),
            file_name="DXF_A3_PDFs.zip",
            mime="application/zip",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "下载合并版 A3 PDF",
            data=merge_pdfs(results),
            file_name="DXF_A3_Combined.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    with st.expander("单独下载", expanded=False):
        for name, data in results:
            st.download_button(name, data=data, file_name=name, mime='application/pdf', key=name)

if errors:
    st.error("以下文件转换失败：")
    for name, msg in errors:
        st.code(f"{name}: {msg}")
    st.warning("常见原因：文件不是 ASCII/Binary DXF、DXF 已损坏、外部参照未绑定、或包含 ezdxf 不支持的代理对象。可在 AutoCAD 中另存为 DXF 2013 后重试。")
