# mall-v2 · 后端服务

Spring Boot 3 多模块单体，包含**管理端**（`mall-admin`，:8080）与**用户端**（`mall-portal`，:8081）两个应用。
完整项目说明、功能清单与部署步骤见[仓库根 README](../README.md)。

## 模块划分

```
mall-v2（父工程 packaging=pom，只做依赖版本管理，不含业务代码）
├── mall-common     公共模块（jar）   CommonResult / ResultCode / 全局异常 / 工具
├── mall-mbg        数据访问模块（jar）实体（model）+ Mapper 接口 + mapper XML
├── mall-service    共享业务模块（jar）跨 admin/portal 的统一业务能力（会员等级、积分）
├── mall-admin      管理端应用（可启动，:8080）
└── mall-portal     用户端应用（可启动，:8081）
```

> `mall-service` 的存在意义：赠分、回冲积分等逻辑同时被「用户端确认收货」和「管理端代确认收货 / 退货完成」触发，
> 下沉到共享模块可避免两个应用各写一份导致口径漂移。

## 用 IDEA 打开

**不要**逐个模块 Open。正确姿势：`File → Open` → 选择本目录的 `pom.xml` → **Open as Project**，
IDEA 会自动识别 `<modules>` 并加载全部模块；随后在 Maven 面板点 **Reload All Maven Projects**。

## 命令行构建与运行

```bash
# 打包（-am 必须带：确保依赖的 mall-common / mall-mbg / mall-service 一并重新构建）
mvn -o -pl mall-admin  -am package -DskipTests
mvn -o -pl mall-portal -am package -DskipTests

# 运行
java -jar mall-admin/target/mall-admin-1.0-SNAPSHOT.jar     # :8080
java -jar mall-portal/target/mall-portal-1.0-SNAPSHOT.jar   # :8081
```

## 配置

- `application.yml`：已脱敏，敏感项均为 `${ENV:默认值}` 占位符，**可直接提交**。
- `application-local.yml`：本地真实配置（数据库 / Redis 密码、OSS AccessKey、JWT 密钥），**已被 .gitignore 忽略**。
  复制同目录的 `application-local.yml.example` 后填写即可；`application.yml` 通过 `spring.profiles.include: local` 自动加载它。

## 技术要点

- **MyBatis-Plus 3.5.7**：单表 CRUD 走 `BaseMapper` / `LambdaQueryWrapper`，复杂查询仍写 XML。
- **统一返回体**：`CommonResult<T>` / `CommonPage<T>`（`total` 为 `Long`）。
- **逻辑删除**：`logic-delete-field: deleteStatus`（品牌 / 分类逻辑删；商品 / SKU 物理删）。
- **鉴权**：Spring Security + JWT；管理端另有 `MenuPermissionInterceptor` 做菜单级接口鉴权。
- **定时任务**：`mall-portal` 通过 `@EnableScheduling` 执行订单自动确认收货。
