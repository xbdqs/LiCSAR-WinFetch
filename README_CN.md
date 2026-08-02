# LiCSAR-WinFetch 中文快速开始

LiCSAR-WinFetch 用于在 Windows 中发现和下载 LiCSAR 产品、支持断点恢复、
建立 LiCSBAS-ready 目录、验证必需的 `unw`/`cc` 文件，并在大规模下载前
利用轻量清单规划多帧时间范围。

软件不执行干涉图生成、时序反演、多帧拼接、跨帧参考统一、大气建模、
升降轨分解或形变解释。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

也可以运行：

```powershell
conda env create -f environment.yml
conda activate licsar_download
```

## 单帧清单检查与下载

先检查 `config_example.json`。示例默认设置为 `dry_run: true`：

```powershell
python download_licsar_windows.py --config config_example.json --dry-run
```

确认帧号、日期范围、产品和输出目录后，再将 `dry_run` 改为 `false`并运行。
未完成文件保存为 `.part`；通过可用的远端大小检查后才改为正式文件名。

## 多帧规划

```powershell
python multiframe_planner.py `
  --frames examples\qilian_metadata_planning\qilianshan_frames.json `
  --start 20141001 --end 20260728 --mode common-period `
  --output Qilian_Multiframe_Plan
```

祁连山22帧示例只进行元数据/清单规划，不下载22帧GeoTIFF。不同相对轨道
默认协调共同日历区间；共同日期和严格共同干涉对主要用于同轨相邻帧。

## 结构验证

```powershell
python verify_licsbas_structure.py data\021D_04972_131213
```

## 测试和图件复现

```powershell
python -m compileall -q .
python -m unittest discover -s tests -v
python paper\figures\Code\plot_all_figures.py
```

`paper/`中包含脱敏后的验证证据、图件源数据、每幅图的独立代码及最终图件。
仓库不包含大型TIFF、本地环境、认证文件或用户本地路径。
