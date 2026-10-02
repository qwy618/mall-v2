-- 会员账号表（mall-portal C 端）
-- 执行方式：在 MySQL 中 source 本文件，或复制粘贴到客户端执行
CREATE TABLE IF NOT EXISTS member (
  id           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '会员ID',
  username     VARCHAR(64)  NOT NULL COMMENT '用户名（登录名）',
  password     VARCHAR(100) NOT NULL COMMENT '密码（BCrypt 加密存储）',
  phone        VARCHAR(20)  DEFAULT NULL COMMENT '手机号',
  nickname     VARCHAR(64)  DEFAULT NULL COMMENT '昵称',
  avatar       VARCHAR(500) DEFAULT NULL COMMENT '头像 URL',
  status       INT          NOT NULL DEFAULT 1 COMMENT '状态：1 正常 0 禁用',
  create_time  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_username (username),
  UNIQUE KEY uk_phone (phone)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '会员账号';
