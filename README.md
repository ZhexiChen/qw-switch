# QW Switch

QW Switch 是一个独立的 macOS 模型切换工具。把 OpenCode Go、Cline Pass 和自定义 OpenAI 兼容接口保存为配置，在千问办公企业版通过官方 BYOK 接入一次，之后从 QW Switch 切换提供商。千问办公使用原版客户端。

- 内置 OpenCode Go 和 Cline Pass 的 DeepSeek V4.1 Flash 预设，也可以填写自己的接口和模型 ID。
- 配置可单独测试、启用和调整思考档位。切换后，下一条请求使用新配置，BYOK 的模型 ID 和接入密钥保持不变。
- 网关支持 Chat Completions、流式响应和工具调用。只有使用这个 BYOK 模型的请求经过 QW Switch。

## 安装和启动

1. 在 [GitHub Releases](https://github.com/ZhexiChen/qw-switch/releases) 的 **Assets** 中下载 Apple Silicon 版 DMG，把 QW Switch 拖到「应用程序」。最低系统要求为 macOS 13。
2. 打开 QW Switch，编辑一个提供商预设或添加自定义配置，填入自己的 API 密钥。
3. 保存后点「测试」，成功后点「启用」。下一条通过网关发出的请求会使用这项配置。

安装包包含 Python 运行时。关掉控制台窗口后，网关随应用继续运行。从应用菜单退出 QW Switch 即可停止网关。配置和密钥保存在当前用户的 `~/Library/Application Support/QW Switch Desktop` 中，密钥文件仅当前用户可读写。

当前 DMG 是未经过 Apple 公证的预发行版。首次启动如果提示无法验证开发者，可在确认下载来源后打开「系统设置 → 隐私与安全性」，为 QW Switch 选择「仍要打开」。参见 [Apple 的首次打开说明](https://support.apple.com/zh-cn/102445)。

## 接入千问办公

企业需已开通 BYOK，由具有模型管理权限的管理员打开「AI 管理 → 模型管理 → 模型目录 → 主模型」。从 QW Switch 复制完整 Endpoint、模型 Key `qw-switch` 和接入密钥，填写后测试、保存并启用，最后在千问办公选择该模型。后续切换上游时，保留此模型 Key 和接入密钥。参见 [千问办公模型目录](https://docs.qwenwork.cn/enterprise-ultimate/models/model-catalog)。

默认 Endpoint 为 `http://127.0.0.1:18747/v1/chat/completions`，可供同一台 Mac 上的 API 客户端调用。如果千问办公在服务端做预检和推理，需填写服务端网络可达的地址。企业可在自有环境启动同一网关，再用现有 HTTPS 反向代理将 `/v1/chat/completions` 转给它。模型接口校验 QW Switch 生成的 Bearer 密钥。配置页面留在本机。参见 [官方 BYOK 接口约定](https://docs.qwenwork.cn/developer/integrations/model-byok/byok-and-search)。

个人版、联网搜索和专项模型由千问办公各自的配置管理。定时任务和微信入口能否使用自定义模型取决于千问办公是否为该入口提供 BYOK 模型选择。

## 从源码运行和构建

用 Python 3.12 启动 `python3.12 gateway.py`，再打开 `http://127.0.0.1:18747/qw-switch`。服务进程可通过 `QW_SWITCH_DATA_DIR` 指定配置目录，通过 `QW_SWITCH_PORT` 指定端口。

在带 Apple Command Line Tools 的 Apple Silicon Mac 上，下载 [Astral Python 3.12.16 构建](https://github.com/astral-sh/python-build-standalone/releases/download/20261110/cpython-3.12.16%2B20261110-aarch64-apple-darwin-pgo%2Blto-full.tar.zst)，然后运行以下命令。脚本验证运行时校验和，并在应用包里保留运行时许可证。

```sh
python3.12 build-macos.py --python-archive /path/to/python.tar.zst --output QW-Switch-0.2.0-macOS-arm64.dmg
```

## 许可证

QW Switch 源码采用 [MIT 许可证](LICENSE)。DMG 内含 Astral 构建的 CPython 和相关依赖，各自的许可证和构建元数据随应用打包。
