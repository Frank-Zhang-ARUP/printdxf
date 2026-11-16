# DXF Batch to A3 PDF (Streamlit)

批量上传 DXF 平面图，自动按绘图范围居中、等比例缩放并输出固定 ISO A3 页面（420 × 297 mm）的矢量 PDF。

## 功能
- 多文件批量上传
- A3 横向/竖向
- 白底黑线或黑底白线
- 留白和最小线宽调节
- 单张 PDF ZIP 下载
- 所有图纸合并为一个多页 PDF
- 单个 PDF 下载
- 重名文件自动编号
- 对轻微 DXF 错误使用 `ezdxf.recover` 尝试修复

## 本地运行

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud
1. 把 `app.py`、`requirements.txt` 推送至 GitHub 仓库根目录。
2. 在 Streamlit Community Cloud 新建 App。
3. Main file path 选择 `app.py`。

## 使用前建议
- 在 AutoCAD 中执行 `AUDIT` 和 `PURGE`。
- 将外部参照 XREF 绑定，或确保参照内容已写入 DXF。
- 输出前将图形放在 Model Space；本版本绘制 Model Space，不读取 Layout/Paper Space 的打印配置。
- 如有 SHX 字体，云端环境可能无法找到同名字体，文字外观可能被替代。可将字体改为常用 TTF，或在部署环境安装相应字体。
- 图纸会按实际几何范围自动缩放。若某个 DXF 中存在远离主体的散点/对象，主体会显得很小，应先清理这些对象。

## A3 尺寸校验
PDF 页面由 Matplotlib 直接设置为 16.5354 × 11.6929 inch（横向），即 420 × 297 mm。代码没有使用 `bbox_inches='tight'`，因此不会把物理页面裁小。


## v2 中文文字修复
- 自动为 DXF 的 TEXT、MTEXT、ATTRIB 所使用的 text style 指定可用 CJK 字体。
- 支持用户直接上传 `.ttf` / `.otf` / `.ttc` 中文字体。
- 原图采用 SHX 而服务器没有该字体时，可用 Noto Sans CJK SC、微软雅黑、黑体等替代。
- 保留 DXF 实体的文字高度、旋转角度、对齐和宽度因子；替代字体后字宽可能与原 SHX 略有差异。
- 若文字实际是 AutoCAD 专用代理对象、外部参照或未绑定对象，需要先在 AutoCAD 中绑定/转换后再上传。


## v3 方框字修复
- 新增 `packages.txt`，在 Streamlit Community Cloud 安装 `fonts-noto-cjk` 和 `fontconfig`。
- 上传字体后复制到 Linux 标准用户字体目录。
- 每次转换前执行 `ezdxf.fonts.fonts.build_system_font_cache()`，避免新增字体未进入 ezdxf 缓存而显示方框。
- DXF text style 改为引用字体文件名，并清除缺失的 Big Font 声明。

部署时请确保 GitHub 仓库根目录同时包含 `packages.txt`。首次部署安装字体可能多花约 1–3 分钟。
