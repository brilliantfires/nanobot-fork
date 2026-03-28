# 安全策略

## 报告漏洞

如果你发现了 nanobot 中的安全漏洞，请按以下方式报告：

1. **不要** 提交公开的 GitHub issue
2. 在 GitHub 上创建私密安全通告，或联系仓库维护者（xubinrencs@gmail.com）
3. 请包含：
   - 漏洞描述
   - 复现步骤
   - 潜在影响
   - 建议修复方式（如有）

我们的目标是在 48 小时内响应安全报告。

## 安全最佳实践

### 1. API Key 管理

**关键**：绝不要把 API key 提交到版本控制中。

```bash
# ✅ 正确：存放在权限受限的配置文件中
chmod 600 ~/.nanobot/config.json

# ❌ 错误：在代码中硬编码密钥或将其提交到仓库
```

**建议：**
- 将 API key 存放在 `~/.nanobot/config.json` 中，并设置文件权限为 `0600`
- 对敏感密钥可考虑使用环境变量
- 生产环境部署建议使用操作系统钥匙串 / 凭据管理器
- 定期轮换 API key
- 开发环境和生产环境使用不同的 API key

### 2. 通道访问控制

**重要**：生产环境中务必配置 `allowFrom` 列表。

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["123456789", "987654321"]
    },
    "whatsapp": {
      "enabled": true,
      "allowFrom": ["+1234567890"]
    }
  }
}
```

**安全说明：**
- 在 `v0.1.4.post3` 及更早版本中，空的 `allowFrom` 表示允许所有用户。从 `v0.1.4.post4` 起，空的 `allowFrom` 默认拒绝所有访问；如需显式允许所有人，请设置为 `["*"]`。
- 你的 Telegram 用户 ID 可通过 `@userinfobot` 获取
- WhatsApp 请使用包含国家区号的完整手机号
- 定期检查访问日志，关注未授权访问尝试

### 3. Shell 命令执行

`exec` 工具可以执行 shell 命令。虽然危险命令模式已被拦截，但你仍应当：

- ✅ 在 agent 日志中审查所有工具使用情况
- ✅ 明确 agent 正在运行哪些命令
- ✅ 使用权限受限的专用用户账户运行
- ✅ 绝不要以 root 身份运行 nanobot
- ❌ 不要关闭安全检查
- ❌ 不要在包含敏感数据的系统上未经仔细审查就直接运行

**被拦截的模式：**
- `rm -rf /` - 删除根文件系统
- Fork bomb
- 文件系统格式化（`mkfs.*`）
- 原始磁盘写入
- 其他破坏性操作

### 4. 文件系统访问

文件操作具备路径穿越保护，但仍建议：

- ✅ 使用专用用户账户运行 nanobot
- ✅ 用文件系统权限保护敏感目录
- ✅ 定期审计日志中的文件操作
- ❌ 不要给予敏感文件无限制访问

### 5. 网络安全

**API 调用：**
- 所有外部 API 调用默认使用 HTTPS
- 已配置超时以防止请求挂起
- 如有需要，可使用防火墙限制出站连接

**WhatsApp Bridge：**
- bridge 绑定在 `127.0.0.1:3001`（仅本机可访问，不对外网开放）
- 在配置中设置 `bridgeToken`，可启用 Python 与 Node.js 间基于共享密钥的认证
- 保护好 `~/.nanobot/whatsapp-auth` 中的认证数据（权限建议 `0700`）

### 6. 依赖安全

**关键**：请保持依赖为最新安全版本。

```bash
# 检查有漏洞的依赖
pip install pip-audit
pip-audit

# 升级到最新安全版本
pip install --upgrade nanobot-ai
```

对于 Node.js 依赖（WhatsApp bridge）：
```bash
cd bridge
npm audit
npm audit fix
```

**重要说明：**
- 请保持 `litellm` 为最新版，以获取安全修复
- 我们已将 `ws` 升级到 `>=8.17.1` 以修复 DoS 漏洞
- 定期运行 `pip-audit` 或 `npm audit`
- 订阅 nanobot 及其依赖的安全通告

### 7. 生产环境部署

用于生产环境时：

1. **隔离运行环境**
   ```bash
   # 在容器或虚拟机中运行
   docker run --rm -it python:3.11
   pip install nanobot-ai
   ```

2. **使用专用用户**
   ```bash
   sudo useradd -m -s /bin/bash nanobot
   sudo -u nanobot nanobot gateway start
   ```

3. **设置正确权限**
   ```bash
   chmod 700 ~/.nanobot
   chmod 600 ~/.nanobot/config.json
   chmod 700 ~/.nanobot/whatsapp-auth
   ```

4. **启用日志**
   ```bash
   # 配置日志监控
   tail -f ./logs/gateway/gateway.log
   ```

5. **使用限流**
   - 在 API 提供商侧配置速率限制
   - 监控异常使用情况
   - 为 LLM API 设置消费上限

6. **定期更新**
   ```bash
   # 每周检查更新
   pip install --upgrade nanobot-ai
   ```

### 8. 开发环境与生产环境

**开发环境：**
- 使用独立 API key
- 用非敏感数据测试
- 开启详细日志
- 使用测试用 Telegram bot

**生产环境：**
- 使用设置了消费上限的专用 API key
- 限制文件系统访问
- 启用审计日志
- 定期做安全审查
- 监控异常活动

### 9. 数据隐私

- **日志可能包含敏感信息** - 请妥善保护日志文件
- **LLM 提供商能看到你的提示词** - 请阅读其隐私政策
- **聊天记录保存在本地** - 请保护 `~/.nanobot` 目录
- **API key 以明文存储** - 生产环境建议使用系统钥匙串

### 10. 事件响应

如果你怀疑发生了安全事件：

1. **立即吊销已泄露的 API key**
2. **检查日志中的未授权访问**
   ```bash
   grep "Access denied" ~/.nanobot/logs/nanobot.log
   ```
3. **检查是否存在异常文件变更**
4. **轮换所有凭据**
5. **升级到最新版本**
6. **向维护者报告事件**

## 安全特性

### 内建安全控制

✅ **输入校验**
- 文件操作具备路径穿越防护
- 危险命令模式检测
- HTTP 请求输入长度限制

✅ **身份验证**
- 基于允许列表的访问控制：在 `v0.1.4.post3` 及更早版本中，空 `allowFrom` 允许所有人；从 `v0.1.4.post4` 起默认拒绝所有人（`["*"]` 显式允许所有人）
- 失败认证尝试会记录日志

✅ **资源保护**
- 命令执行超时（默认 60 秒）
- 输出截断（10KB 限制）
- 所有外部 API 调用使用 HTTPS
- Telegram API 使用 TLS
- WhatsApp bridge：仅监听 localhost，并支持可选 token 鉴权

## 已知限制

⚠️ **当前安全限制：**

1. **没有速率限制** - 用户可以发送无限消息（如有需要请自行补充）
2. **明文配置** - API key 以明文存储（生产环境请使用 keyring）
3. **没有会话管理** - 不会自动让会话过期
4. **命令过滤有限** - 只会拦截明显危险的模式
5. **审计链路不足** - 安全事件日志仍较有限（如有需要请自行增强）

## 安全检查清单

部署 nanobot 前，请确认：

- [ ] API key 已安全存储（不在代码中）
- [ ] 配置文件权限已设为 `0600`
- [ ] 所有通道都已配置 `allowFrom`
- [ ] 以非 root 用户运行
- [ ] 文件系统权限已正确收紧
- [ ] 依赖已更新到最新安全版本
- [ ] 日志已被监控以捕获安全事件
- [ ] API 提供商侧已配置速率限制
- [ ] 已具备备份和灾难恢复方案
- [ ] 已对自定义技能 / 工具进行安全审查

## 更新

**最后更新**：2026-02-03

获取最新安全更新与公告，请查看：
- GitHub Security Advisories: https://github.com/HKUDS/nanobot/security/advisories
- Release Notes: https://github.com/HKUDS/nanobot/releases

## 许可证

详见 LICENSE 文件。
