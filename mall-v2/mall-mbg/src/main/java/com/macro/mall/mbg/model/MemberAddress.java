package com.macro.mall.mbg.model;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("member_address")
public class MemberAddress {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private Long memberId;
    private String receiverName;
    private String phone;
    private String province;
    private String city;
    private String district;
    private String detailAddress;
    private Integer defaultStatus;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
