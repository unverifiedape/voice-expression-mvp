# RelationshipTest V1.6.9 标准部署版（安全 + Analytics）

本包是完整覆盖版，基于你上传的当前运行版本生成，保留原页面与原 API，只新增：

- `/api/track` 前端埋点接口
- `/admin/analytics` 安全数据面板
- SQLite 本地数据库 `analytics.db`
- 分享页访问、播放、回流、生成分享追踪
- 标准 Nginx 配置，避免 `/admin/analytics` 被首页吞掉
- systemd 中加入 `ANALYTICS_ADMIN_TOKEN`

## 推荐上线方式

```bash
cd /opt
cp -r voice-expression-mvp voice-expression-mvp-backup-$(date +%Y%m%d-%H%M%S)
unzip -o relationshiptest_v169_standard_secure_analytics.zip -d /opt/voice-expression-mvp
cd /opt/voice-expression-mvp
chmod +x install_secure_analytics.sh
./install_secure_analytics.sh '换成你自己的强密码token'
```

## 访问数据面板

```text
https://showmecard.com/admin/analytics?token=你的token
```

如果没有带 token，会显示登录页。

## 验证

```bash
curl http://127.0.0.1:8010/health
curl 'http://127.0.0.1:8010/admin/analytics?token=你的token' | head
sudo journalctl -u voice-expression -n 80 --no-pager
```

## 这次重点修复

之前 `/admin/analytics` 显示首页，是路由没有正确进到 FastAPI 或 admin 路由没有部署成功。本包同时修复两层：

1. FastAPI 明确新增 `/admin/analytics`
2. Nginx 标准配置统一代理到 `127.0.0.1:8010`，不会再把 `/admin/analytics` fallback 成首页
