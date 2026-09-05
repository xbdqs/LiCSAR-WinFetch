# LiCSAR-WinFetch

LiCSAR-WinFetch 是用于 LiCSAR 产品获取、断点续传、LiCSBAS-ready 目录组织、结构检查和多帧时间规划的开源 Python 工具。

本项目最初面向 Windows 用户的实际获取需求开发，但核心代码使用 Python 的跨平台路径、网络和文件操作。`v1.3.0` 审稿修订版已在 Windows、Ubuntu Linux 和 macOS 上分别以 Python 3.10 和 3.12 完成 CI 验证，6/6 组合全部通过。Windows 批处理文件仅为便利启动器，核心 Python 命令为跨平台实现。

软件不负责生成干涉图、时序反演、多帧拼接、跨帧参考统一、大气建模、升降轨 LOS 分解或地球物理解释。

## 当前修订版新增的验证工具

`reviewer_validation/` 包含三组审稿回复所需的可复现工具：

1. **106D 四模式零下载比较**：比较 independent、common-period、common-epochs、common-pairs，并计算节点、边、连通分量、最大连通分量、孤立日期、平均度、cycle rank、时间基线等；
2. **20/20 文件 SHA-256**：对受控 benchmark 清单中的全部 20 个文件计算 SHA-256；
3. **LiCSAR-WinFetch vs LiCSBAS Step 01 等价性比较**：比较相同 20 个 LiCSAR 对象的存在性、大小和 SHA-256，不做速度比较。

## 本地零下载测试

Windows：

```text
RUN_REVISION_CHECKS.bat
```

Linux/macOS：

```text
./run_revision_checks.sh
```

该步骤不会下载 22 帧 GeoTIFF，也不会执行大型网络下载。

完整操作顺序见：

```text
REVIEWER_REVISION_TESTING_GUIDE_CN.md
```

## 版本原则

- `v1.2.4`：初次投稿时的固定 Release，应保留，不删除、不覆盖；
- `v1.3.0`：审稿修订正式版本，加入跨平台验证、106D 四模式比较、20/20 SHA-256 与 LiCSBAS Step 01 对照证据。
