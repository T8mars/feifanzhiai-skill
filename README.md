# 非凡之爱人物替换 · No Ordinary Love

## 调用入口与优惠

| 平台 | 入口 | 优惠 |
| --- | --- | --- |
| 贞贞 AI | [贞贞 AI 调用](https://www.zzai.app) | 免费 GPT Image 2.6 |
| RunningHub | [国内站](https://www.runninghub.cn?inviteCode=kol01-rh099) · [国际站](https://www.runninghub.ai?inviteCode=rh-v1121) | 每日 3 次免费 H3 及优惠券 |
| 晨羽 | [晨羽调用](https://www.chenyu.cn/console/login?invitationCode=NGT5S4) | T8 专属优惠券，见下表 |

| 晨羽优惠 | 数量或领取条件 | 券码 |
| --- | --- | --- |
| 0.1 = 5 | 300 张 | `W6TGFF` |
| 30 = 45 | 300 张 | `T8AIGC` |
| 50 = 100 | 每位粉丝均可领取，每个账号限领一次 | `50VS50` |

更多镜像陆续更新，可搜索 **t8star**。

**简体中文** | [English](README.en.md)

> 选择 **RunningHub（RH）** 渠道时，需要自己的 RH 账号、API Key 与可用余额：[国际站注册](https://www.runninghub.ai/?inviteCode=rh-v1121) · [中国站注册](https://www.runninghub.cn?inviteCode=kol01-rh099)。也支持使用独立 Key 的[贞贞 AI 渠道](https://api.seedance.nz/sign-up?aff=5f4w)。注册及安装技能本身不会提交生成任务。

将两张人物参考图映射到《非凡之爱》固定原片的两个动作角色，保留原片动作、镜头、场景和节奏，完成分段生成、候选修复、逐帧复核、配乐对齐与最终合片。

这是一个供支持 `SKILL.md` 的 Agent 使用的技能包，附带可执行 Python 工具。**专用于这一套 19 段模板，不是任意视频的一键换脸软件。**

| 项目 | 说明 |
| --- | --- |
| 技能版本 | 3.1.0 |
| 调用名称 | `$no-ordinary-love-character-replacement` |
| 中文名称 | 非凡之爱人物替换 |
| 原片规格 | 19 段、1417 个保留帧、24 fps，成片约 59.04 秒 |
| 生成渠道 | RunningHub；贞贞 AI `minimax-h3-comfyui-charswap` · 晨羽工作流 |
| 并发与切分 | 晨羽每次串行运行一个指定镜头，其他云渠道本项目合计最多 3 路生成；按原镜头切分，含补齐帧的输入也不得超过 10 秒 |
| 本仓库包含 | 技能说明、运行脚本、修复经验、离线测试 |
| 需自行准备 | 原始复刻包、两张人物图、本地配乐、自己的 API 凭据、FFmpeg |

## 能做什么

- 用新人物复用同一原片，或按要求交换两个角色的映射。
- 先做身份和高风险试片，再按空位展开生成；共享队列满时等待。
- 少量问题镜头采用三种有诊断差异的方案并行修复，保留稳定镜头。
- 通过本地任务 ID 恢复查询和下载，避免断线后重跑整批。
- 单独保存对齐 WAV；仅换音乐时复用画面，不重生成视频。
- 记录包含补齐帧、返工与未入选候选的实际成本。

### 3.0 的关键改进

正式合片增加**候选联合复核**：身份、人数、道具归属、动作节奏、服装交接、肢体遮挡、画面瑕疵和前后衔接必须逐项记录。复核记录绑定候选、运动源和身份图的哈希，更换任一文件后旧记录失效。

例如，013 是双人溅水保护镜头：必须保留两人，由一号动作角色撑伞，披衣属于二号。不能因为修好了衣服，就忽略另一角色消失或撑伞者变了。

脚本检查的是**实际复核记录是否完整且对应当前文件**，不自动识别人脸、人数或雨伞。实际画面判断仍需 Agent 检查与原速观看。详见[联合复核说明](references/quality-review.md)。

## 用晨羽跑一个镜头

准备好工作副本、该段运动源、人物图、提示词和本地配乐后，指定晨羽渠道与段号。例如在工作副本中验证双人镜头 015：

```powershell
python SKILL_DIR/scripts/bootstrap_runtime.py --project WORK_DIR --apply --provider chenyu --key-file PRIVATE_KEY_FILE
python WORK_DIR/chenyu_workflow.py 015
```

把占位符换成本机路径，Key 文件放在技能与工作副本之外。运行器逐个上传运动视频与本段参考图，按角色顺序填入工作流，锁定发布修订版并保存订单。断线后重复同一命令即可续查。输出为 `WORK_DIR/完成分段/015.mp4`。已验证该镜头返回 73 帧、24 fps。费用读取订单最终结算金额及平台原始单位。[晨羽工作流文档](https://chenyu.mintlify.site/api-reference/workflow/introduction)

## 开始前准备

1. **原始复刻包**：从原作者的合法来源取得《非凡之爱》复刻包，保留原始许可与署名；另建工作副本。至少保留 `补齐生成用`、帧数表、逐段简介、提示词模板、工作流与应用配置、原段音轨和 `LICENSE.txt`。源动画作者为 **antrofrog**；复刻包与原工作流来源为 [wuwukasi](https://space.bilibili.com/670281046)。
2. **两张人物图**：默认一号图映射源片的一号动作角色，二号图映射二号；需要对调时明确说明。原图保持只读，单双人任务的图片槽位由 Agent 按帧数表设置。
3. **本地配乐**：公开版不附带源视频、音乐、人物图或本次成片。请准备有权使用、长度足够的音频，先生成约 59.04 秒的对齐 WAV。
4. **运行环境**：推荐 Windows、Python 3.10+，安装 `requirements.txt`；FFmpeg/ffprobe 使用原包便携版或系统 PATH 中的版本。
5. **渠道凭据**：所选渠道（RH、贞贞 AI 或晨羽）的个人 Key，仅保存到本机私有文件。每次新人物制作确认渠道；同一项目续跑沿用已选渠道。

## 安装

下载本仓库 ZIP，解压后将技能目录命名为 `no-ordinary-love-character-replacement`，放入 Agent 的技能目录。Codex 用户也可在 PowerShell 中运行：

```powershell
$skillRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
git clone https://github.com/T8mars/feifanzhiai-skill.git (Join-Path $skillRoot 'no-ordinary-love-character-replacement')
```

已存在同名目录时先保留自己的修改，不要覆盖正在运行的项目。依赖安装命令在本仓库根目录执行：

```powershell
python -m pip install -r requirements.txt
```

## 最简单的使用方法

给 Agent 两张图片、原片工作副本路径和音乐文件路径，再说明渠道即可，例如：

```text
使用 $no-ordinary-love-character-replacement 制作《非凡之爱》。
工作副本：E:/VideoWork/NoOrdinaryLove
图1替换一号，图2替换二号，保留参考图风格。
渠道：RunningHub。Key 已保存在工作副本的 api_key.txt。
音乐：E:/Music/soundtrack.wav，请另存对齐版。
保留原动作、镜头、节奏；检查人数、撑伞者和衣物交接后合片。
```

如需贞贞 AI，改为“渠道：贞贞 AI，Key 在本机私有文件路径”，由 Agent 用 `--key-file` 引用。不要把实际 Key 写进 README、提交记录或分享包。

Agent 会检查素材、对齐音乐、离线安装运行文件、重写 19 段提示词，然后进行试片、生成、修复与验收。**真正提交生成任务会消耗对应服务的余额。**

## 手动运行参考

下面使用占位路径；请改为自己的路径。`SKILL_DIR` 指本技能目录，`WORK_DIR` 指原片的独立工作副本。

### 1. 先对齐本地音乐

```text
python SKILL_DIR/scripts/prepare_audio.py --project WORK_DIR --input LOCAL_MUSIC.wav --output WORK_DIR/配乐/已对齐.wav --set-default
```

公开版不含内置音乐，因此首次安装运行文件前需要这一步。已有有效 `delivery_audio.json` 时会沿用；无需重新裁剪。原始音乐与对齐版分别保存。

### 2. 安装对应渠道的运行文件

RH：

```text
python SKILL_DIR/scripts/bootstrap_runtime.py --project WORK_DIR --apply --provider runninghub
```

将自己的 RH Key 仅保存在工作副本的 `api_key.txt`，保留原包的应用及工作流配置。贞贞 AI：

```text
python SKILL_DIR/scripts/bootstrap_runtime.py --project WORK_DIR --apply --provider zhenzhen_ai --key-file LOCAL_PRIVATE_KEY_FILE
```

安装器不联网、不生成，会备份旧脚本并保留已有音乐、凭据与任务状态。无内置音乐又未配置本地音乐时，会在改写运行文件前停止并给出提示。

### 3. 提示词就绪后试片

以下命令在 `WORK_DIR` 执行；参考图和本次 19 段提示词需先准备完成。

```text
# RH：初始试片
python rh_batch.py submit 003 004 015

# 贞贞 AI：先报价，再试片
python zhenzhen_batch.py quote 003 004 015
python zhenzhen_batch.py run 003 004 015
```

通常采用 003/004/015 检查身份；长裙、长发等高风险参考图会调整试片组合。不要同时启动两个渠道，也不要在同一项目启动多个三路调度器。续跑先读状态和锁；RH 使用 `status`/`download` 查询已有任务，贞贞 AI 沿用 `run` 恢复。

### 4. 复核后合片

```text
python quality_review.py prepare --project WORK_DIR
python quality_review.py check --project WORK_DIR
python assemble.py --check-only
python assemble.py
```

`prepare` 只准备待查记录；由 Agent 实际复核后填写，用户无需手工编辑 JSON。正式选片覆盖全部 19 段、已知问题解决、逐帧及原速复核完成后才合片。待审预览使用独立清单并标注缺陷，不能冒充验收完成。

## 输出与成本

最终输出包括约 59.04 秒的视频、独立对齐 WAV、选片及复核记录；原始素材和候选保留在工作副本。固定成片名为 `非凡之爱_final_Made-by-wuwukasi.mp4`，输出保留原作者许可与署名 metadata。

贞贞 AI 账本读取任务最终结算的 `usage`，按任务 ID 去重：

```text
实际每生成秒成本 = 全部任务最终实扣 ÷ 全部实际生成视频秒数
```

分母包含返工、废弃候选和补齐尾帧，不能只用最终成片时长。不同币种分开统计。成功未下载或结算缺失时不声称已得到最终单位成本。RH 按任务实扣核对；接口返回 `null` 时费用未知，不能记为 0，也不能用共享 Key 的余额变化代替本项目花费。仓库不承诺固定价格或固定生成耗时。

## 常见问题

| 问题 | 处理方式 |
| --- | --- |
| 队列满了 | 等服务端真实空位；本项目合计最多 3 路，不取消其他项目任务。 |
| 007/008 在贞贞 AI 失败 | 此渠道输入需至少 2 秒；运行器会在运动副本尾部补齐，最终仍按原始 37/34 帧留片。 |
| 断线或下载失败 | 保留状态与任务 ID；恢复查询或下载，不重新付费提交整批。 |
| 人物少了或撑伞者错误 | 复查源动作角色映射与全部关键帧；衣服正确不代表整段合格。 |
| 合片提示缺复核记录 | 由 Agent 完成真实检查，不把待查项批量改成通过来绕过。 |
| 只想换音乐 | 使用 `scripts/replace_music.py` 复用已有成片画面，另存新版本。 |

## 开发与验证

```text
python -B -X utf8 -m unittest discover -s tests -v
```

目前有 20 项离线测试，覆盖候选复核、错误动作归属、文件变更失效、费用统计、断线恢复及无音乐公开版安装。测试不调用生成服务、不读取真实凭据，不代替视频画面验收。

仓库只维护本技能。`.gitignore` 排除 Key、私有配置、任务与输出目录、媒体及 `ROADMAP.MD`；发布前还需检查实际待提交文件。

## 致谢与许可

- **源动画作者：antrofrog**。
- **复刻包及原工作流作者：[wuwukasi](https://space.bilibili.com/670281046)**。感谢原作者提供的复刻包与规则。
- **优化作者：[T8star](https://space.bilibili.com/385085361)**：双渠道调度、帧数适配、恢复与费用统计、音乐对齐、修复经验和候选联合复核。

本仓库保留原包的 [LICENSE.txt](LICENSE.txt)，采用其中的自定义使用与分发条款，**不是 MIT/Apache 许可**。第三方素材权利归各自权利人；源片、音乐和参考图不随本仓库分发。使用时保留作者、来源、许可及要求的成片 metadata。

## T8star 相关链接

[B 站](https://space.bilibili.com/385085361) · [YouTube](https://www.youtube.com/@T8star-Aix/) · [API 注册](https://api.seedance.nz/sign-up?aff=5f4w) · [免费画廊](https://www.openzhenzhen.com) · [在线 AI 应用](https://www.runninghub.ai/zh-cn/user-center/1907375370302308353/userPost?inviteCode=rh-v1121) · [ComfyUI 整合包](https://pan.quark.cn/s/264edb7e36bd) · [Hugging Face](https://huggingface.co/t8star)

部分注册及邀请链接包含推广参数。
