# No Ordinary Love · Character Replacement Skill

## Service links and offers

| Service | Access | Offer |
| --- | --- | --- |
| Zhenzhen AI | [Open Zhenzhen AI](https://www.zzai.app) | Free GPT Image 2.6 |
| RunningHub | [Mainland China](https://www.runninghub.cn?inviteCode=kol01-rh099) · [International](https://www.runninghub.ai?inviteCode=rh-v1121) | Three free H3 runs per day, plus coupons |
| Chenyu | [Open Chenyu](https://www.chenyu.cn/console/login?invitationCode=NGT5S4) | T8-exclusive coupons listed below |

| Chenyu offer | Availability | Coupon code |
| --- | --- | --- |
| 0.1 = 5 | 300 coupons | `W6TGFF` |
| 30 = 45 | 300 coupons | `T8AIGC` |
| 50 = 100 | Available to every fan, once per account | `50VS50` |

Search for **t8star** to find new mirror sites as they are added.

[简体中文](README.md) | **English**

> The **RunningHub (RH)** channel requires your own account, API key and available credits: [International site](https://www.runninghub.ai/?inviteCode=rh-v1121) · [China site](https://www.runninghub.cn?inviteCode=kol01-rh099). Alternatively, use the [Zhenzhen AI channel](https://api.seedance.nz/sign-up?aff=5f4w) with a separate key. Registering or installing this skill does not submit generation jobs.

Replace the two action roles in the fixed *No Ordinary Love* template using two character reference images. Preserve the source choreography, camera, scene and timing while managing generation, repair candidates, visual review, soundtrack alignment and final assembly.

This repository is a skill for agents that support `SKILL.md`, with executable Python helpers. **It is designed for this specific 19-segment source package, not arbitrary videos.**

| Item | Details |
| --- | --- |
| Skill version | 3.1.0 |
| Invocation | `$no-ordinary-love-character-replacement` |
| Chinese display name | 非凡之爱人物替换 |
| Template | 19 segments, 1,417 retained frames, 24 fps, approximately 59.04 seconds |
| Providers | RunningHub; Zhenzhen AI `minimax-h3-comfyui-charswap` · Chenyu Workflow |
| Scheduling | One named shot at a time on Chenyu, up to 3 jobs on the other cloud channels; shot-based segments with a 10-second input limit, including padding |
| Included | Skill instructions, runtime scripts, repair guidance and offline tests |
| Required locally | Original source package, two reference images, soundtrack, your credentials and FFmpeg |

## Run one shot with Chenyu

Prepare the work copy, motion clip, reference images, shot prompt and local music. To try the two-character shot 015, substitute your own paths:

```powershell
python SKILL_DIR/scripts/bootstrap_runtime.py --project WORK_DIR --apply --provider chenyu --key-file PRIVATE_KEY_FILE
python WORK_DIR/chenyu_workflow.py 015
```

Keep the key file outside the skill and work copy. The runner uploads each input, binds the references in shot order, pins the published revision and saves the order. Repeat the same command to resume. The result is `WORK_DIR/完成分段/015.mp4`. Shot 015 returned 73 frames at 24 fps in the verified trial. Read the settled amount in the unit returned by the platform. [Chenyu Workflow API](https://chenyu.mintlify.site/api-reference/workflow/introduction)

## Features

- Reuse the source template with new characters or an explicitly swapped role mapping.
- Verify identity and high-risk shots before expanding generation; wait when a shared queue is full.
- Compare three diagnostically different repair approaches for problematic shots while retaining stable results.
- Resume queries and downloads using existing task IDs after an interruption.
- Save a separately reusable aligned WAV; replace music without regenerating video.
- Account for padding, discarded candidates and repair attempts in actual generation costs.

### What changed in 3.0

Final assembly now requires a **joint candidate review**: identity, subject count, prop ownership, action and timing, garment transfer, anatomy and occlusion, artifacts, and continuity. Records are bound to the hashes of the candidate, motion source and reference images. Changing those inputs invalidates the previous review.

For example, shot 013 must retain both roles: source role 1 operates the umbrella and source role 2 retains the transferred outer garment. Fixing clothing does not justify approving a missing partner or the wrong umbrella operator.

The script validates **inspection records and their file bindings**. It does not automatically recognise faces, people or umbrellas. The agent must still inspect actual frames and review playback at normal speed. See the [joint review guide](references/quality-review.md), currently in Chinese.

## Prerequisites

1. **Original source package.** Obtain the *No Ordinary Love* remake package from an authorised source and create an independent work copy. Preserve its source clips, frame tables, shot descriptions, prompt templates, workflow/application configuration, source audio and `LICENSE.txt`. The source animation is by **antrofrog**; the remake package and original workflow are by [wuwukasi](https://space.bilibili.com/670281046).
2. **Two character images.** Image 1 maps to source action role 1 and image 2 to role 2 unless you request a swap. References remain read-only. The agent configures each single-person or two-person task according to the frame table.
3. **Local soundtrack.** The public repository does not include footage, music, character references or production outputs. Supply audio you are entitled to use, long enough for the approximately 59.04-second video.
4. **Runtime.** Windows and Python 3.10+ are recommended. Install `requirements.txt`. Use the source package's portable FFmpeg/ffprobe or executables available on PATH.
5. **Your own credentials.** Choose RH, Zhenzhen AI or Chenyu and store the key in a private local file. A new character run confirms the provider; a resumed project keeps its existing provider.

## Installation

Download the repository ZIP, extract it, rename the skill folder to `no-ordinary-love-character-replacement`, and place it in your agent's skills directory. Codex users can also run this in PowerShell:

```powershell
$skillRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
git clone https://github.com/T8mars/feifanzhiai-skill.git (Join-Path $skillRoot 'no-ordinary-love-character-replacement')
```

If that directory already exists, preserve your changes rather than overwriting an active installation. From the repository root, install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Quick start

Give your agent the two images, the work-copy path, the soundtrack path and your provider choice:

```text
Use $no-ordinary-love-character-replacement to remake No Ordinary Love.
Work copy: E:/VideoWork/NoOrdinaryLove
Image 1 replaces source role 1; image 2 replaces source role 2.
Keep the reference characters' visual style.
Provider: RunningHub. My key is stored locally in the work copy's api_key.txt.
Music: E:/Music/soundtrack.wav. Save a separate aligned version.
Preserve source choreography, camera and timing. Verify both characters,
the umbrella operator and garment transfer before final assembly.
```

For Zhenzhen AI, specify that provider and a private key-file path; the agent references it with `--key-file`. Never put a real key in a README, commit or shared archive.

The agent checks assets, aligns music, installs local helpers, rewrites the 19 prompts, then runs trials, generation, repairs and review. **Submitting generation jobs consumes credits from the selected service.**

## Manual workflow

Replace the following placeholders with your actual paths. `SKILL_DIR` is this skill's directory; `WORK_DIR` is an independent copy of the original source package.

### 1. Align local music first

```text
python SKILL_DIR/scripts/prepare_audio.py --project WORK_DIR --input LOCAL_MUSIC.wav --output WORK_DIR/配乐/已对齐.wav --set-default
```

The public release has no bundled music, so do this before the initial runtime installation. An existing valid `delivery_audio.json` is reused. Keep the original music and aligned WAV separately.

### 2. Install helpers for your provider

RH:

```text
python SKILL_DIR/scripts/bootstrap_runtime.py --project WORK_DIR --apply --provider runninghub
```

Store your RH key only in `api_key.txt` within the local work copy, and retain the original package's application and workflow configuration. Zhenzhen AI:

```text
python SKILL_DIR/scripts/bootstrap_runtime.py --project WORK_DIR --apply --provider zhenzhen_ai --key-file LOCAL_PRIVATE_KEY_FILE
```

The installer operates offline, backs up replaced scripts and preserves configured music, credentials and task state. With no bundled or configured audio, it stops before modifying runtime files and explains the missing setup step.

### 3. Generate trials after preparing prompts

Run the following from `WORK_DIR` after preparing the references and all 19 prompts for the current characters:

```text
# RH: initial trials
python rh_batch.py submit 003 004 015

# Zhenzhen AI: estimate, then generate trials
python zhenzhen_batch.py quote 003 004 015
python zhenzhen_batch.py run 003 004 015
```

The usual identity trials are 003/004/015. Long skirts, hair and other risks may change the trial selection. Do not run multiple providers or multiple three-worker schedulers in one project. Read existing state and locks before resuming. RH uses `status`/`download` for existing jobs; Zhenzhen AI resumes through `run`.

### 4. Review and assemble

```text
python quality_review.py prepare --project WORK_DIR
python quality_review.py check --project WORK_DIR
python assemble.py --check-only
python assemble.py
```

`prepare` creates pending inspection records. The agent fills them after real inspection; users do not need to edit JSON manually. Final assembly requires all 19 selected segments, resolved known issues, complete retained-frame inspection and normal-speed review. An unfinished preview uses a separate selection manifest and clearly lists known defects.

## Deliverables and costs

Deliverables include the approximately 59.04-second video, a separate aligned WAV, and selection/review records. Source files and candidates stay in the local work copy. The final filename is `非凡之爱_final_Made-by-wuwukasi.mp4`, retaining the required attribution and license metadata.

Zhenzhen AI accounting uses settled task `usage`, deduplicated by task ID:

```text
Actual cost per generated second = total settled charges / all actual generated video seconds
```

The denominator includes repairs, discarded candidates and padding. It is not merely the final edit's duration. Currencies are reported separately. Missing settlement data or undownloaded successful outputs prevent a final unit-cost claim. RH charges must be matched to individual tasks; `null` means unknown, not zero. A shared key's balance change is not an accurate project bill. No fixed price or generation-time guarantee is made.

## Troubleshooting

| Issue | Action |
| --- | --- |
| Queue full | Wait for actual server capacity; keep this project's total at most 3. Do not cancel other projects' tasks. |
| Zhenzhen AI rejects 007/008 | Inputs require at least 2 seconds. The runner tail-pads a motion copy while retaining only the original 37/34 frames in the edit. |
| Connection or download failure | Keep task IDs and state; resume the existing job rather than paying for a replacement batch. |
| Missing character or wrong umbrella operator | Compare source roles and all key frames. Correct clothing alone is insufficient. |
| Missing review record blocks assembly | Complete the actual inspection; do not bulk-mark pending checks as passed. |
| Music-only change | Use `scripts/replace_music.py` to reuse existing video and save a new output. |

## Development and validation

```text
python -B -X utf8 -m unittest discover -s tests -v
```

The current 20 offline tests cover candidate review, incorrect role ownership, stale file bindings, accounting, recovery and public installation without bundled music. They do not call generation services, read real credentials or replace visual acceptance.

This repository contains only this skill. `.gitignore` excludes keys, private configuration, job/output directories, media and `ROADMAP.MD`. Inspect the actual publication file list before every release.

## Credits and license

- **Source animation: antrofrog**.
- **Original remake package and workflow: [wuwukasi](https://space.bilibili.com/670281046).** Thank you for the original package and workflow rules.
- **Optimisations: [T8star](https://space.bilibili.com/385085361).** Provider routing, frame adaptation, recovery/accounting, audio alignment, repair guidance and joint candidate review.

The original [LICENSE.txt](LICENSE.txt) is preserved. Its custom usage and redistribution terms apply; this is **not an MIT or Apache license**. Third-party materials remain owned by their respective rights holders and are not distributed here. Preserve the author, source, license and required final-video metadata.

## T8star links

[Bilibili](https://space.bilibili.com/385085361) · [YouTube](https://www.youtube.com/@T8star-Aix/) · [API registration](https://api.seedance.nz/sign-up?aff=5f4w) · [Free gallery](https://www.openzhenzhen.com) · [Online AI apps](https://www.runninghub.ai/zh-cn/user-center/1907375370302308353/userPost?inviteCode=rh-v1121) · [ComfyUI bundle](https://pan.quark.cn/s/264edb7e36bd) · [Hugging Face](https://huggingface.co/t8star)

Some registration and invitation links contain referral parameters.
