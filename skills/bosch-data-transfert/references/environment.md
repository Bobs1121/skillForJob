# 环境 / 权限 / 地址速查（通用 CR 数据 + arbe）

> 本 skill 刻意**不在 SKILL.md 里写死服务器/路径**。下表是 CR60/BYD 项目的一组
> **典型示例值**，供 AI 参考或回填到 profiles；**实际值以用户指定 / profiles 配置为准**。
> 每个新项目复制 `profiles/_template.yml` 填自己的值即可。

## 服务器（不唯一，示例）

| 项 | 示例值 |
|----|--------|
| 主机 | `10.190.171.44` |
| 主机名 | WX-C-001QM |
| 系统 | Ubuntu (Linux 5.15, x86_64) |
| 用户 | `hoz2wx` |
| SSH | 免密密钥 `~/.ssh/id_ed25519`，SSH config 已配 |
| 工作区根 | `~/CR60LIGHT/` |
| 分析工作区 | `~/CR60LIGHT/cr60_light_arbe/`（ROS catkin） |
| 数据目录 | `~/CR60LIGHT/data/qzh/<TR号>/` |
| 磁盘 | 935G 总量，约 360G 可用 |

## 数据源（UNC → 本地）

- SMB 共享 `//abtvdfs2.de.bosch.com/ismdfs` 挂载到 Linux `/mnt/cluster`
- UNC → Linux：`\\abtvdfs2.de.bosch.com\ismdfs\loc\szh\...` → `/mnt/cluster/loc/szh/...`
- Windows 兜底盘：`\\abtvdfs2.de.bosch.com\ismdfs\loc\szh` = `P:`
- 典型数据路径：`/mnt/cluster/loc/szh/Isilon2/TestackData/Driving_APP/08_BYD/47_CR60light/02_QZH/06_RCTB/`
- 数据文件：`corner_radar_net_*.bag`（0.25–1.4GB）

## 环境变量（Windows 本地）

| 变量 | 用途 |
|------|------|
| `BOSCH_TR_KEY` | TR/Jira 访问（44 字符；MCP `bosch-rsd` 用到） |
| `BOSCH_PR_KEY` | Bitbucket 代码仓访问（49 字符；HTTP Bearer token） |

## TR 问题单（Jira）

- 访问：MCP `bosch-rsd`（`mcp__bosch-rsd__tr_*`），不要 curl 直连（内网 DNS 不解析 tr.de/jira.de）。
- TR 号：`CRGVI-xxxx`（问题单）、`CRGVBYDPF-xxxxx`（内部开发单）。
- 附件：`tr_get_issue` 返回 attachments 数组（如 CRGVI-1848 有 `.blf` + `.png`）。

## 代码仓（Bitbucket）

| 项 | 示例值 |
|----|--------|
| 项目 / 仓库 | `CR60_EVO / cr60_light` |
| 浏览 URL | `https://sourcecode06.dev.bosch.com/projects/CR60_EVO/repos/cr60_light/browse` |
| API base | `https://sourcecode06.dev.bosch.com/rest/api/1.0/` |
| 认证 | `-H "Authorization: Bearer $BOSCH_PR_KEY"` |
| tag 示例 | `BYD_UKE_BL03RC02.7`、`BYD_UKE_BL03RC02.8`、`BYD_UKE_BL04RC01.0/1/2` |
| G列→tag | `BL03RC02.7_S`→`BYD_UKE_BL03RC02.7`；去 `_S`、加 `BYD_UKE_` |
| Linux git remote | `ssh://git@sourcecode01.de.bosch.com:7999/cr60_evo/cr60_light.git` |

常用 API：
```bash
# 列 tag
curl -sk -H "Authorization: Bearer $BOSCH_PR_KEY" \
  "https://sourcecode06.dev.bosch.com/rest/api/1.0/projects/CR60_EVO/repos/cr60_light/tags?limit=100"
# 列分支
curl -sk -H "Authorization: Bearer $BOSCH_PR_KEY" \
  "https://sourcecode06.dev.bosch.com/rest/api/1.0/projects/CR60_EVO/repos/cr60_light/branches?limit=50"
```

## arbe 分析工作区

- 主仓：`~/CR60LIGHT/cr60_light_arbe/`（ROS catkin）
- `src/algo_source/`：`cr60_light` 代码 submodule
- 分析时把 `algo_source` 切到 G 列对应 tag。

## 车型 → sheet（CUDA yaml 54 行）

| 车型目录 | yaml sheet |
|---------|-----------|
| BYD_UKE | 03_QZH |
| BYD_SC6H | 03_QZH |
| （其他） | 常见：00_SC2E/01_SA3/02_PA/03_QZH/04_EWE/05_MR |

CUDA 表：内仓 `coem/<车型>/tools/container_input/08_CustData/CUDA_*.xlsx`

## 网络

- Bosch 内网经 px 代理（127.0.0.1:3128）出公网；内网域名（*.bosch.com）直连。
- 内网 DNS `10.53.53.53` 不解析公共域名，也不解析 `tr.de.bosch.com`/`jira.de.bosch.com`。
- `sourcecode06.dev.bosch.com` → 内网 IP `10.73.26.210`（可直连）。
- CA 证书：`C:\tools\cacert.pem`（curl 需 `-k` 或 `CURL_CA_BUNDLE`）。