# swu-checkin

一个用于钉钉相关签到流程的自动化脚本项目。  
脚本入口为 `scripts/check_in.py`。由于西南大学官方统一身份认证系统（CAS）启用了网宿盾 UKEY / WAF 防护以及图形验证码，本项目已升级为使用 **Playwright 无头浏览器** 绕过 WAF，并集成 **ddddocr** 自动识别验证码。

本项目已全面支持**多账户同时签到**。

## 目录结构

```text
.
├── scripts/
│   ├── check_in.py      # 主程序入口（支持单/多账号循环签到）
│   ├── get_info.py      # Playwright 登录、自动识别验证码及 Token 获取模块
│   ├── verify.py        # 令牌校验模块
│   └── des.py           # DES 加密模块
├── users.json.example   # 多账号配置文件示例
├── Dockerfile           # Docker 镜像构建文件
├── docker-compose.yml   # Docker Compose 配置文件
├── requirements.txt     # Python 依赖包列表
└── .github/workflows/swu-check.yml # GitHub Actions 工作流
```

## 环境要求 & 依赖安装

- Python 3.10+
- 依赖：`requests`、`playwright`、`ddddocr`
- 系统图形库依赖：在 Linux 系统中，`ddddocr` 依赖的 OpenCV/ONNX 以及 Playwright 需要安装相应的系统库（如 `libgl1`, `libglib2.0-0`）。

### 安装方式

```bash
# 安装 Python 库依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器内核
playwright install chromium
```

## 账号配置方式

脚本支持以下三种方式配置账号（优先级从高到低）：

### 1. 配置文件 `users.json`（推荐，方便多账号管理）
在项目根目录下创建 `users.json` 文件：
```json
[
  {
    "username": "你的校园网账号1",
    "password": "你的密码1"
  },
  {
    "username": "你的校园网账号2",
    "password": "你的密码2"
  }
]
```

### 2. 环境变量 `SWU_USERS`（JSON 字符串格式，适合 Docker / 容器环境）
```bash
export SWU_USERS='[{"username": "校园网账号1", "password": "密码1"}, {"username": "校园网账号2", "password": "密码2"}]'
```

### 3. 单账号环境变量 `SWU_USERNAME` / `SWU_PASSWORD`（向下兼容）
```bash
export SWU_USERNAME="你的校园网账号"
export SWU_PASSWORD="你的密码"
```

## 运行方式

### 本地 / VPS 直接运行
```bash
python scripts/check_in.py
```

### 使用 Docker 部署
通过卷映射挂载 `users.json` 或者直接在 `.env` 中指定 `SWU_USERS` 环境变量，然后使用 Docker Compose 启动：
```bash
docker-compose up --build
```

详细的 VPS 部署指南（包含 Docker、原生部署及 Cron 定时任务配置）请参考：[vps_deployment_guide.md](file:///C:/Users/Sky_C/.gemini/antigravity/brain/cb01c1eb-a5df-41d3-a5ae-2e5b08ddee02/vps_deployment_guide.md)

## GitHub Actions 自动运行

项目提供了 `.github/workflows/swu-check.yml` 每日定时打卡工作流：
- 每天北京时间 21:10 自动执行
- 支持手动触发

### 配置步骤
1. 进入 GitHub 仓库 `Settings` -> `Secrets and variables` -> `Actions`。
2. 新增以下 `Repository secrets` 之一：
   - 若是多账号，添加 `SWU_USERS`，值为 JSON 数组字符串，例如：`[{"username":"校园网账号1","password":"密码1"},{"username":"校园网账号2","password":"密码2"}]`。
   - 若是单账号，添加 `SWU_USERNAME` 和 `SWU_PASSWORD`。

## 返回状态说明

`scripts/check_in.py` 执行后对每个账号输出其结果：
- `0`：今日暂无签到任务
- `1`：签到成功
- `2`：今日已签到，无需重复操作
- `3`：账号密码验证失败
- `4`：连接错误或请求超时
- `5`：请假中，请检查是否有打卡任务
