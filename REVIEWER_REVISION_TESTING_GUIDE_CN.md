# SOFTX-D-26-00981 审稿修订：代码重新上传与验证操作指南

## 0. 先明确一件事

**不要删除 GitHub 仓库本身，也不要删除 `v1.2.4` tag / Release。**

`v1.2.4` 是初次投稿时的固定版本，后续回复审稿人需要保留这个历史证据。现在只需要把仓库 `main` 分支更新为 `1.3.0-rc1` 审稿修订候选版。完成所有真实验证以后，再创建正式 `v1.3.0` Release。

## 1. 这次完整包中已经包含什么

- 三个核心程序；
- 原 15 项确定性测试；
- Windows / Ubuntu / macOS 的 GitHub Actions 工作流；
- 祁连山 22 帧 metadata-only 原始 inventory 与绘图数据；
- 初次投稿使用的 LiCSBAS Step 02 脱敏证据；
- Reviewer 1 Comment 3 的 106D 四模式零下载分析脚本；
- Reviewer 1 Comment 5 的 WinFetch vs LiCSBAS Step 01 文件等价性比较脚本；
- Reviewer 1 Comment 6 的 20/20 SHA-256 脚本；
- 受控 benchmark 的 20 文件精确清单；
- 一键本地零下载检查脚本。

包内不包含 22 帧大型 GeoTIFF，也不包含 benchmark 的大型栅格。

## 2. 重新上传前，本地先解压检查

解压后应进入：

```text
LiCSAR-WinFetch/
```

根目录必须直接看到：

```text
.github/
README.md
README_CN.md
LICENSE
CITATION.cff
download_licsar_windows.py
multiframe_planner.py
verify_licsbas_structure.py
tests/
validation/
reviewer_validation/
examples/
paper/
RUN_REVISION_CHECKS.bat
```

不要把外层 ZIP 本身上传为仓库内容。

## 3. 推荐的 GitHub 更新方式

最稳妥的方法是使用 Git / GitHub Desktop 更新现有仓库，而不是删除仓库重新建。

如果使用 GitHub Desktop：

1. Clone 现有仓库 `https://github.com/xbdqs/LiCSAR-WinFetch`；
2. 在本地仓库目录中保留隐藏的 `.git` 目录；
3. 删除除此之外的旧工作树文件；
4. 把本完整包中 `LiCSAR-WinFetch/` **里面的全部内容**复制进去；
5. GitHub Desktop 会显示文件新增/修改/删除；
6. Commit summary 填：

```text
Prepare v1.3.0-rc1 reviewer revision candidate
```

7. Commit to main；
8. Push origin。

如果只使用 GitHub 网页，也可以更新，但不建议为了“干净”而删除整个 repository。

## 4. 上传后先看 GitHub Actions

进入：

```text
GitHub repository → Actions → deterministic-tests
```

应当看到 6 个组合：

```text
Windows + Python 3.10
Windows + Python 3.12
Ubuntu + Python 3.10
Ubuntu + Python 3.12
macOS + Python 3.10
macOS + Python 3.12
```

不要预设它们会通过。

- 全绿：截图整个 Actions 页面反馈；
- 有红叉：点击失败 job，再点击红色 step，把错误日志截图或复制反馈；
- 黄色：等待结束。

## 5. Windows 本地先做零下载检查

在解压后的仓库根目录，打开 CMD 或 Anaconda Prompt：

```bat
cd /d D:\你的路径\LiCSAR-WinFetch
```

确保依赖已安装后运行：

```bat
RUN_REVISION_CHECKS.bat
```

这个命令依次执行：

- Python版本/系统信息；
- `compileall`；
- 三个 CLI `--help`；
- 全部 deterministic unit tests；
- 106D 四模式零下载分析。

如果成功，末尾显示：

```text
ALL LOCAL ZERO-DOWNLOAD CHECKS PASSED.
```

并生成：

```text
reviewer_outputs/
├─ Reviewer1_C3_106D_Mode_Metrics.csv
├─ Reviewer1_C3_106D_Mode_Summary.json
└─ Reviewer1_C7_106D_Isolated_Common_Epochs.csv
```

把终端最后约 50 行和整个 `reviewer_outputs` 文件夹压缩后反馈。

## 6. 此时先停止，不要进行 benchmark 下载

在完成步骤 4 和 5 并反馈以前，先不要：

- 重新下载 22 帧数据；
- 运行 LiCSBAS Step 01 对照下载；
- 创建 `v1.3.0` Release；
- 修改论文 Word；
- 修改审稿回复中的真实结果数字。

下一阶段会根据你实际的 GitHub Actions 和本地结果，再一步一步完成 20/20 SHA-256 和 LiCSBAS Step 01 等价性验证。
