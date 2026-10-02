-- 008: 售后退货申请单(order_return_apply) + 订单操作流水(order_operate_history)
-- 联动债务7：退款金额取 order_item.real_amount，本脚本只建表，金额计算在业务层。
-- 可重复执行：全部使用 CREATE TABLE IF NOT EXISTS。

CREATE TABLE IF NOT EXISTS order_return_apply (
  id                  BIGINT        NOT NULL AUTO_INCREMENT,
  order_id            BIGINT        NOT NULL,
  order_sn            VARCHAR(64)   DEFAULT '',
  member_id           BIGINT        NOT NULL,
  return_amount       DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '退款金额=Σ(real_amount×退数/行数)',
  reason              VARCHAR(200)  DEFAULT '',
  description         VARCHAR(500)  DEFAULT '',
  proof_pics          VARCHAR(1000) DEFAULT '' COMMENT '凭证图URL数组(JSON字符串)',
  return_items        TEXT          COMMENT '退货明细JSON:[{orderItemId,skuId,productId,productName,productPic,quantity,realAmount}]',
  status              TINYINT       NOT NULL DEFAULT 0 COMMENT '0待审核 1已同意 2已拒绝 3已收货 4已完成 5已关闭',
  handle_note         VARCHAR(500)  DEFAULT '',
  handle_man          VARCHAR(64)   DEFAULT '',
  company_address     VARCHAR(200)  DEFAULT '' COMMENT '退货收货地址(管理端同意时填)',
  return_tracking_no  VARCHAR(64)   DEFAULT '' COMMENT '会员回填的退货物流单号',
  create_time         DATETIME      DEFAULT CURRENT_TIMESTAMP,
  update_time         DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_order_id  (order_id),
  KEY idx_member_id (member_id),
  KEY idx_status    (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='售后退货申请单(债务14)';

CREATE TABLE IF NOT EXISTS order_operate_history (
  id            BIGINT        NOT NULL AUTO_INCREMENT,
  order_id      BIGINT        NOT NULL,
  order_sn      VARCHAR(64)   DEFAULT '',
  operate_man   VARCHAR(64)   DEFAULT '' COMMENT '操作人:会员端=会员{memberId},管理端=管理员用户名',
  operate_type  VARCHAR(32)   DEFAULT '' COMMENT 'CREATE/PAY/CANCEL/SHIP/CONFIRM/RETURN_APPLY/RETURN_APPROVE/RETURN_REJECT/RETURN_RECEIVE/RETURN_COMPLETE',
  operate_note  VARCHAR(500)  DEFAULT '',
  create_time   DATETIME      DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_order_id (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单操作流水/审计留痕(债务13)';
