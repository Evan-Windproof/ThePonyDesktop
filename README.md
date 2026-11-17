# The Pony Desktop v0.1.2

HoofTTY 的实验性原生 Ring 3 图形桌面，以 C 实现，不使用宿主操作系统图形 API。

已实现纯色桌面、软件鼠标光标、演示窗口、标题栏拖动、关闭按钮和底部任务栏。
按 **Q** 或点击右下角 **EXIT [Q]** 返回 HoofTTY Shell，再执行 `run tpd` 可重新进入。
关闭演示窗口不会退出桌面；v0.1.0 不提供重新打开窗口的按钮。

## 架构边界

TPD 不是由 Shell 直接调用的内核桌面函数。`src/tpd.c` 单独编译为 ELF，再转为固定地址平坦映像。
HoofTTY 现有加载器分配代码页和栈页，以 Ring 3 启动应用；显示与输入通过 `int 0x82` 调用内核服务。
窗口、命中检测、拖动、任务栏和光标绘制策略都位于用户应用。

**这是受限的、随系统镜像打包的用户态应用，不是支持外部安装的通用可执行文件。**
当前没有文件系统/通用 ELF 加载器，映像仍通过 `.incbin` 存在系统镜像中。
代码页为 User/RX，栈为 User/RW/NX，各 4 KiB；只有一个活跃用户任务，共享 CR3。
不能将其描述为独立进程地址空间、动态加载软件或完整桌面环境。

详见 [源码审计与方案](docs/architecture.md)、[接口](docs/abi.md)、[当前升级测试](docs/v0.1.2.md)（[v0.1.0运行记录](docs/validation.md)）。

## v0.1.2 集成与升级

[升级设计、测试及限制](docs/v0.1.2.md)。本版本不改动图形或输入算法。
`integration/manage.py` 先完整识别原始基线、v0.1.0、v0.1.1 或已安装v0.1.2，再决定写入。
已知旧桌面源码可以升级；未知本地修改会在写入前拒绝，仓库其他文件及暂存区保持不变。

```sh
./integration/apply.sh ../HoofTTY --check   # 只读预检
./integration/apply.sh ../HoofTTY           # 安装/升级；输出恢复备份路径
make version
make check-integration
```

版本信息以 `VERSION` 为源。`python3 scripts/version.py --set 0.1.3` 同步更新README标题；
集成时生成 `apps/tpd_version.h`，源码启动消息和任务栏共用此宏，Makefile依赖确保改版本后重编译应用。
历史补丁和测试记录保持原版本，不做全仓库字符串替换。

## 构建

已核对的 HoofTTY 基线：`8d2951186df48773d6014290f08be9ebf0df8257`。
准备 GCC/binutils、Make、Python 3、Git、xorriso；运行测试还需要 QEMU、GDB。
Debian/Ubuntu 可使用 HoofTTY 的 `scripts/setup-host.sh`（需要管理员权限）。
首次构建会下载固定版本 Limine 并验证上游记录的 SHA256；不要关闭校验。

```sh
git clone https://github.com/Evan-Windproof/HoofTTY.git
# 将 HoofTTY 与本仓库放在同级目录；已有检出时不要重复克隆或覆盖本地改动
cd ThePonyDesktop
make HOOFTTY=../HoofTTY
make check HOOFTTY=../HoofTTY
make test HOOFTTY=../HoofTTY
make run HOOFTTY=../HoofTTY
```

`make` 调用集成管理器，使用经过核对的历史接口补丁构造目标文件集；不要再手工叠加补丁。
需要本地 HoofTTY Git 对象中存在上述基线提交，缺失或出现未知接口状态时会安全报错。
当前版本沿用 v0.1.1 内核图形接口，只增加应用版本头的构建依赖。
Python 3 是集成脚本的必要工具；源码包包含旧版应用的哈希和回归测试夹具，不要求TPD完整Git历史。

预检会验证全部受管理文件、ABI和应用源码，再备份并逐文件替换。遇到未知修改请先自行保存并合并，
不要使用 reset 清理自己的工作。普通异常会回滚；断电/SIGKILL等中断不保证自动恢复，详见升级文档。
直接修改 TPD 后再次运行集成，已安装的不同源码会被视为未知修改，请先自行核对同步；脚本不会覆盖开发中的代码。

产物：`HoofTTY/build/apps/tpd.elf`、`tpd.bin`、`HoofTTY/build/kernseed.iso`。
在客户机 Shell 输入：

```text
hoof> apps
hoof> run tpd
```

`make headless` 的宿主 stdin 不是客户机键盘；自动化测试使用 QMP 注入键盘/鼠标事件。
没有鼠标/可用 framebuffer 时拒绝启动并返回 Shell，不降级为内核桌面演示。
图形模式由 Limine 建立，TPD 接管已有 framebuffer；没有实现运行时分辨率切换。
退出时恢复终端渲染并清屏，原有文字历史不恢复；文字颜色与终端字体不改变。

## 文件与交付

- `src/`：桌面 C 源码及现有 HoofTTY 调用约定头文件。
- `integration/`：可审阅的 HoofTTY 修改补丁及安全重放脚本；包含新内核服务源码。
- `tests/`：绘图边界宿主测试、真实 QEMU 图形交互测试。
- `docs/evidence/`：本次运行的串口、GDB、构建与结果记录。

当前工作区的 `/workspace/HoofTTY` 已实际应用同一补丁，便于直接运行；移植到其他机器不依赖该目录快照。
代码及版本标签发布状态以仓库为准；不涉及云环境发布。

## 限制与后续方向

仅支持 PC i8042 标准三字节 PS/2 鼠标、RGB 32bpp framebuffer；支持 400×300 至 1024×768 的后备缓冲模式。
输入保留有界按钮边沿队列，同按钮状态的移动合并；队列满时丢弃最旧状态，没有滚轮/USB 输入。
用户应用仍构建完整画面，内核后备缓冲累积修改并按脏包围盒比较提交；没有垂直同步，仍可能撕裂。不存在 GPU 加速、多窗口应用或多任务桌面。
提供单一演示窗口，ASCII 字体复用内核已有原创字形，没有第三方主题/图片。

建议依次开发：显示会话故障与硬件兼容回归测试、带溢出语义的输入队列、脏矩形/双缓冲，
再引入版本化应用 ABI、多页映像加载及可校验的外部模块/文件加载。
将通用加载器作为独立 OS 工作推进，避免把桌面交互逻辑搬回内核。

本项目及适配补丁采用 GPL-3.0-or-later，见 [LICENSE](LICENSE)。
`src/abi.h` 复用 HoofTTY；字体和驱动修改基于 HoofTTY 的 GPL 源码。无新第三方运行时依赖。
附件 Kernseed Phase 7 教程仅作参考，旧教程的许可示例、命令名称和历史测试数据未用作当前实现或测试结论。
