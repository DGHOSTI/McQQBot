# Minecraft QQ 机器人

一个围绕 Minecraft 的 QQ 群/私聊机器人：查询服务器状态（含 SRV 解析）、
展示玩家**本地 3D 渲染**的皮肤/头像/披风图（走路姿势、双层皮肤、抗锯齿）。

## ✨ 功能

| 指令 | 别名 | 说明 |
|---|---|---|
| `/server [地址]` | `/status` | 服务器状态（支持 SRV / `host:port`，服务器设置图标时附带图标图） |
| `/skin <玩家名>` | | 玩家皮肤 3D 全身图（走路姿势，双层皮肤） |
| `/head <玩家名>` | | 3D 立体头像 |
| `/cape <玩家名>` | | Mojang 原版披风背面 3D 展示 |
| `/profile <玩家名>` | `/uuid` | UUID / 皮肤模型 / 是否有原版披风 |
| `/ping [地址]` | | 纯延迟测试 |
| `/list [地址]` | | 在线玩家名单（需服务器开启 `enable-query`） |
| `/help` | `/菜单` | 指令总览 |

- **群聊**：可直接发指令（普通消息），也可 `@机器人` 发指令
- **私聊**：直接发指令
- 机器人被拉入新群时自动发送 `/help`

## 🚀 快速开始

### 环境要求

- Windows / Linux / macOS
- Python 3.10+
- 一个通过 QQ 开放平台审核的机器人（具备 C2C、群聊消息权限）

### 安装

```bash
# 1. 创建虚拟环境
python -m venv .venv

# 2. 安装依赖（Windows PowerShell 用 .venv\Scripts\activate）
source .venv/bin/activate

pip install -r requirements.txt
```

`requirements.txt` 内容见下文“依赖”。

> 若使用 [uv](https://github.com/astral-sh/uv)：
> `uv venv .venv && uv pip install -r requirements.txt`

### 配置

复制 `config.example.yaml` 为 `config.yaml`，并填入你的机器人凭据：

```bash
cp config.example.yaml config.yaml   # Windows: copy config.example.yaml config.yaml
```

编辑 `config.yaml`：

```yaml
appid: "你的机器人AppID"
secret: "你的机器人AppSecret"

# MC 机器人配置(可选)
default_server: "mc.example.com"   # /server、/ping、/list 缺省地址；可不配
mc_timeout: 5                      # 服务器检测超时(秒)
```

### 运行

```bash
python main.py
```

启动后日志统一写入 `logs/bot.log`（按天轮转保留 14 天），控制台同步输出。

## 🔐 权限

- **当前所有指令普通用户即可使用**（群聊/私聊均可用，无需管理员）。
- 已内置**权限框架**，为后续管理员专属指令预留：
  - 指令注册时若带 `permission="admin"`，则只有配置中的管理员可执行；
  - 管理员专属指令不会出现在 `/help` 普通帮助中；
  - 管理员账号在 `config.yaml` 的 `admin_user_openids`（私聊）/
    `admin_group_openids`（群聊）中登记。
- 查询自己的 openid：任意发一条指令，从 `logs/bot.log` 中
  `[指令] ... 发送者=xxx` 即可看到。

## 🧩 目录结构

```
.
├── main.py          # 入口：日志 → botpy 兼容补丁 → 配置 → 依赖组装 → 启动
├── config.yaml      # 配置（凭据 + 默认服务器等）
├── bot/             # QQ 机器人应用层（唯一接触 botpy 的层）
│   ├── client.py        # McBotClient：事件接收、群消息去重、分发
│   ├── compat.py        # botpy 补丁：支持「群聊普通消息」事件
│   ├── commands.py      # Command / CommandDispatcher（注册-解析-分发）
│   ├── handlers.py      # 指令业务（依赖注入装配）
│   ├── messaging.py     # ReplyChannel：群/私聊统一发送
│   ├── uploader.py      # ImageHost：本地图 → 匿名图床 → 公网 URL
│   ├── logging_setup.py # 统一日志（logs/）
│   └── config.py        # BotConfig(dataclass)
├── mc_core/         # Minecraft 领域层（纯逻辑，不依赖 QQ，可单独复用）
│   ├── server.py        # ServerProbe / ServerIconService
│   ├── player.py        # PlayerService：UUID / 玩家档案
│   ├── render.py        # SkinRenderer：3D 皮肤渲染（走路姿势/头像/披风）
│   ├── formatter.py     # 状态文本格式化
│   ├── net.py           # HttpClient（共享会话/图片探测）
│   ├── text.py          # MOTD/颜色代码清理
│   └── cli.py           # 命令行检测工具
├── vendor/          # vendored 第三方库
│   └── minepi/          # MinePI (MIT)：皮肤 3D 渲染库
└── logs/            # 运行日志
```

依赖方向为单向分层：`main → bot → mc_core`，`mc_core` 与 `bot`、`vendor` 相互独立，
各模块可通过 `build_dispatcher(...)` 做依赖注入。

## 🖼 皮肤渲染说明

`/skin`、`/head`、`/cape` 的图片不是官方皮肤文件，也不是外站 3D 图，
而是**本地实时渲染**（Pillow + MinePI）：

- 自动按玩家名解析正版 UUID，拉取 Mojang 皮肤纹理
- 渲染为 3D 立体模型（含**双层皮肤**层、头发层）
- 走路姿势 / 背面披风等姿态可调
- 2× 超采样抗锯齿 + 圆角渐变背景，输出整洁图片
- 渲染角度等默认参数在 `mc_core/render.py` 顶部的 `DEFAULT_POSE` 中

渲染出的本地 PNG 通过匿名图床（uguu.se）转存为公网 URL 后再发送到 QQ，
因此**需要机器能访问 `uguu.se`**。

## 🧪 命令行检测工具（可选）

不需要启动机器人时，也可直接检测服务器：

```bash
python -m mc_core.cli mc.example.com --query --json
```

## 📦 依赖

```
botpy            # QQ 官方机器人 SDK
mcstatus         # Minecraft 服务器状态探测
aiohttp          # 异步 HTTP
PyYAML           # 配置解析
Pillow           # 图像处理（渲染后处理）
numpy            # MinePI 依赖
```

> `vendor/minepi/` 为随仓库分发（vendored）的第三方库，
> 源自 [benno1237/MinePI](https://github.com/benno1237/MinePI)（MIT License）。

## ⚠️ 注意事项与限制

- **皮肤查询限正版账号**：离线模式（非正版服）玩家的名字在 Mojang 无档案，
  无法解析 UUID/皮肤，指令会给出提示。
- `/list` 需要服务器在 `server.properties` 开启 `enable-query=true`。
- `/server` 的服务器图标仅在服务端放置 `server-icon.png` 时显示。
- `/cape` 仅支持 Mojang 原版披风的 3D 渲染；第三方披风（Optifine/LabyMod 等）
  不在查询范围内。
- 群聊普通消息依赖 `bot/compat.py` 对 botpy 的补丁，升级 botpy 后请留意。
- 私聊/群聊的图片发送依赖图床中转，若 `uguu.se` 不可达会提示稍后再试。

## 📜 License

本项目代码部分遵循 MIT。第三方库 `vendor/minepi/` 遵循其自身 MIT License。
