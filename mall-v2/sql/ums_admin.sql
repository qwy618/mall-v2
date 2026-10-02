-- 阶段4：后台管理员表
-- 在 mall_v2 库中执行（MySQL 8.x）
CREATE TABLE IF NOT EXISTS ums_admin (
    id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    username    VARCHAR(64)  NOT NULL COMMENT '用户名',
    password    VARCHAR(255) NOT NULL COMMENT '密码（BCrypt 加密）',
    icon        VARCHAR(500) DEFAULT NULL COMMENT '头像',
    email       VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
    nick_name   VARCHAR(64)  DEFAULT NULL COMMENT '昵称',
    note        VARCHAR(500) DEFAULT NULL COMMENT '备注',
    create_time DATETIME     DEFAULT NULL COMMENT '创建时间',
    login_time  DATETIME     DEFAULT NULL COMMENT '最后登录时间',
    status      INT(1)       DEFAULT 1 COMMENT '账号状态：1-启用 0-禁用',
    PRIMARY KEY (id),
    UNIQUE KEY uk_username (username)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '后台管理员表';

-- 种子管理员：admin / macro123
-- 幂等写入：依赖 uk_username 唯一键，重复执行不会插入重复行。
-- 密码为 BCrypt(macro123) 的哈希（前缀 $2b$10$，Spring Security BCryptPasswordEncoder 兼容）。
INSERT IGNORE INTO ums_admin (username, password, nick_name, status, create_time)
VALUES ('admin', '$2b$10$890AQ//C1nzVWowFoG5Z9eDZZk2FzQN8gXaabPBgdSv03hHMPEkj6', '系统管理员', 1, NOW());
