<p align="center"><img src="docs/icon.png" width="128" alt="Subveil 图标"></p>

<h1 align="center">Subveil</h1>

<p align="center">
在任意 HDMI 输入上叠加外挂字幕，由 Home Assistant 驱动。<br>
<a href="README.md">English</a>
</p>

Subveil 在 Android TV 显示的画面上叠加同步字幕，包括 Apple TV 等 HDMI 输入。电视上的小 App 在屏幕底部绘制透明悬浮窗；Home Assistant 集成跟随你的媒体播放器，从 OpenSubtitles 匹配字幕，并让字幕与播放进度保持同步。

```
Apple TV ──(Home Assistant 媒体播放器)──> Home Assistant ──HTTP :8765──> Subveil App（电视悬浮窗）
                                              │
                                              └──> OpenSubtitles.com
```

## 功能

- 在 HDMI 输入和 Android TV / Google TV 上的任意 App 之上显示字幕。
- 开始播放新片时自动搜索（电影按片名，剧集按剧名 + 季 + 集），按片名完全匹配、语言优先级和下载量排序。
- 在 Home Assistant 中切换字幕、微调时间、修改字号；偏移和选择按片源记忆。
- 可以从 Home Assistant 或电视 App 提供的网页上传自己的 SRT、WebVTT、ASS/SSA 字幕，支持 UTF-8、UTF-16 和 GBK 编码。
- 字幕总开关：在网页上或 Home Assistant 的 `switch.subveil_subtitles` 一键开关所有字幕，电视会记住这个设置。
- 开机自动启动；电视 App 重启后自动恢复字幕。

## 两个版本

| | **Subveil**（配合 Home Assistant） | **Subveil 独立版** |
|---|---|---|
| APK | `subveil-x.y.z.apk` | `subveil-standalone-x.y.z.apk` |
| 播放同步 | 从 Home Assistant 媒体播放器自动同步 | 从已配对的 Apple TV 自动同步，或使用网页上的手动计时 |
| 字幕搜索 | 开始播放新片时自动搜索 | Apple TV 播放新片时自动搜索，或在网页上按片名搜索 |
| 控制方式 | Home Assistant 实体和动作 | 电视提供的网页 `http://<电视IP>:8765` |

两个版本的包名不同（`io.github.kgymhina.subveil` 和 `io.github.kgymhina.subveil.standalone`），但使用同一个端口，请只安装其中一个。

### 独立版快速上手

1. 安装 `subveil-standalone-x.y.z.apk` 并授予悬浮窗权限：

   ```sh
   adb install subveil-standalone-0.3.0.apk
   adb shell appops set io.github.kgymhina.subveil.standalone SYSTEM_ALERT_WINDOW allow
   adb shell am start-foreground-service -n io.github.kgymhina.subveil.standalone/io.github.kgymhina.subveil.OverlayService
   ```

   详见 [授予悬浮窗权限](#授予悬浮窗权限必需每台电视一次)。
2. 在手机或电脑上打开 `http://<电视IP>:8765`，按 **测试悬浮窗显示** 确认电视上能看到文字。
3. 在 **设置** 中保存 OpenSubtitles API Key 和语言（例如 `zh-cn,en`）。
4. 如果用 Apple TV 看片：在 **Apple TV** 区域按 **查找 Apple TV**，再按 **配对**，输入 Apple TV 屏幕上显示的 PIN。之后 Subveil 会跟随 Apple TV 的播放：每部新片自动加载字幕，并保持时间同步。开始播放和结束播放时，屏幕上会各显示一条简短提示，停止播放后字幕会隐藏。
5. 其它信号源：搜索片名，在结果上按 **使用**，视频开始时按 **开始**。有偏差时用跳转按钮、**设为此时间** 或偏移来修正。

调整时间可以用偏移按钮，也可以直接输入秒数（例如 `-2.5`）并按 **设置偏移**。偏移值按字幕文件记忆。

语言使用 OpenSubtitles 的代码。中文请写 `zh-cn`（简体）、`zh-tw`（繁体）、`ze`（中英双语）或 `zh-ca`（粤语）。

Apple TV 支持通过 [Chaquopy](https://chaquo.com/chaquopy/) 在电视上运行 [pyatv](https://github.com/postlund/pyatv)，因此独立版 APK 约 40 MB。Apple TV 和电视需要在同一个局域网。

本文其余部分介绍 Home Assistant 版本。
## 授予悬浮窗权限（必需，每台电视一次）

Android TV 没有「显示在其他应用上层」的设置页面，所以 Subveil 无法在屏幕上申请这个权限。安装后需要通过 ADB 授权一次：

1. 在电视上开启 **开发者选项**（设置 → 设备偏好设置 → 关于 → 连按 **版本号** 7 次），然后在开发者选项中打开 **USB 调试** / **网络调试**。不同品牌的菜单名称略有不同。
2. 在电脑上连接电视并授权。请使用你安装的版本对应的包名：

   ```sh
   adb connect <电视IP>:5555        # 第一次连接时需要在电视上确认

   # Home Assistant 版
   adb shell appops set io.github.kgymhina.subveil SYSTEM_ALERT_WINDOW allow
   # 独立版
   adb shell appops set io.github.kgymhina.subveil.standalone SYSTEM_ALERT_WINDOW allow
   ```

3. 检查是否成功，输出中应包含 `allow`：

   ```sh
   adb shell appops get io.github.kgymhina.subveil.standalone SYSTEM_ALERT_WINDOW
   ```

4. 启动服务（或打开一次 App），然后打开 `http://<电视IP>:8765`，按 **测试悬浮窗显示**。电视底部会显示 5 秒测试文字。如果页面提示悬浮窗未生效，请重复第 2 步并重新启动服务。

没有字幕需要显示时悬浮窗是透明的，所以安装后屏幕上什么都看不到是正常的，可以用 **测试悬浮窗显示** 来检查。

更新 App 或重启电视后权限仍然有效，卸载后需要重新授权。

已测试：小米电视（HyperOS，Android 14）、索尼 BRAVIA（Android 9）。
## 要求

- Android 8.0 及以上的 Android TV，并开启 ADB 调试（只用于一次性授予悬浮窗权限）。
- Home Assistant 2026.3 及以上，并有对应信号源的媒体播放器实体，例如 [Apple TV 集成](https://www.home-assistant.io/integrations/apple_tv/)。
- [OpenSubtitles.com API Key](https://www.opensubtitles.com/en/consumers)（免费）。

悬浮窗能否显示在 HDMI 画面上取决于电视型号。已在小米电视（HyperOS，Android 14）+ Apple TV 和索尼 BRAVIA（Android 9）上测试通过。

## 1. 安装电视 App

1. 从 [最新 Release](https://github.com/Kgym-Hina/Subveil/releases/latest) 下载 `subveil-x.y.z.apk`。
2. 通过 ADB 安装并授予悬浮窗权限：

   ```sh
   adb connect <电视IP>:5555
   adb install subveil-0.1.0.apk
   adb shell appops set io.github.kgymhina.subveil SYSTEM_ALERT_WINDOW allow
   adb shell am start-foreground-service -n io.github.kgymhina.subveil/.OverlayService
   ```

3. 在浏览器打开 `http://<电视IP>:8765`，确认 App 正在运行。

建议在路由器中给电视分配固定 IP。

> **小米电视：** 系统会在你离开 App 界面时结束带悬浮窗的 App。Subveil 会在自己的界面打开时暂时移除悬浮窗，离开 3 秒后恢复。直接启动服务（上面最后一条 `adb` 命令）可以完全避开这个问题。如果重启后没有自动启动，请在电视设置中允许 Subveil 自启动。

## 2. 安装 Home Assistant 集成

### HACS

[![在 HACS 中打开此仓库](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Kgym-Hina&repository=Subveil&category=integration)

或者在 HACS 菜单中选择 **Custom repositories**，以 **Integration** 类型添加 `https://github.com/Kgym-Hina/Subveil`，下载 **Subveil** 后重启 Home Assistant。

### 手动安装

把 `custom_components/subveil` 复制到 Home Assistant 的 `config/custom_components/`，然后重启。

### 配置

进入 **设置 → 设备与服务 → 添加集成 → Subveil**，填写：

| 字段 | 说明 |
|---|---|
| 电视 IP / 端口 | 运行 Subveil 的电视，端口 `8765` |
| 媒体播放器 | 字幕跟随的播放器，例如 `media_player.ke_ting_apple_tv` |
| OpenSubtitles API Key | 在 opensubtitles.com → API consumers 创建 |
| 用户名 / 密码 | 可选。API Key 不允许匿名下载时需要 |
| 字幕语言 | 逗号分隔、按优先级排序，例如 `zh-cn,en` |
| 自动搜索 | 开始播放新片时自动搜索并加载最匹配的字幕 |

除电视地址外，其它选项之后都可以在 **配置** 中修改。

## 实体

| 实体 | 作用 |
|---|---|
| `select` 字幕 | 在搜索结果和上传的字幕之间切换，或关闭字幕 |
| `number` 字幕偏移 | 单位秒，正数表示字幕延后；按片源记忆 |
| `button` 字幕提前 / 延后 1 秒、0.1 秒 | 快速微调；电视上会短暂显示新的偏移 |
| `button` 重新搜索 | 按当前片名重新搜索 |
| `text` 搜索关键词 | 输入片名手动搜索 |
| `sensor` 状态 | 当前状态；属性中包含电视是否在线、片名和字幕文件名 |

## 动作

- `subveil.upload_subtitle`：通过 `path` 加载文件（必须位于允许的目录，例如 `/media` 或 `/config/www`），或用 `content` 直接传入字幕文本。
- `subveil.search`：在 OpenSubtitles 搜索；不填 `query` 时使用当前片名。
- `subveil.set_text_size`：设置字号（1080p 屏幕像素）。

## 同步原理

Home Assistant 提供播放器的 `media_position` 和 `media_position_updated_at`。Subveil 在播放、暂停、拖动进度时把位置发送给电视，并每 10 秒校准一次；两次同步之间由电视 App 自己计时。停止播放时隐藏字幕。

信号源只提供片名，不提供版本和年份，所以偶尔会匹配到其它版本。此时请在列表中换一个，或调整偏移。

## 从源码构建

Android App 使用 Gradle 构建。Home Assistant 版没有第三方依赖；独立版通过 Chaquopy 打包了 Python 和 pyatv。

```sh
# 需要 JDK 17、Android SDK，以及 Python 3.11（构建独立版时）
cd android
./build.sh                        # 构建两个版本，使用自动生成的调试密钥签名
VARIANT=ha ./build.sh             # 只构建 Home Assistant 版
SUBVEIL_BUILD_PYTHON=python3.11 VARIANT=standalone ./build.sh   # 只构建独立版
./install.sh          # 安装到通过 adb 连接的电视
```

设置 `SUBVEIL_KEYSTORE`、`SUBVEIL_KEYSTORE_PASS`、`SUBVEIL_KEY_ALIAS` 可以用自己的密钥签名。

集成测试：

```sh
pip install -r requirements_test.txt
pytest
```

## 许可证

[MIT](LICENSE)。字幕由 [OpenSubtitles.com](https://www.opensubtitles.com) 提供；Subveil 与 OpenSubtitles 无关联。
