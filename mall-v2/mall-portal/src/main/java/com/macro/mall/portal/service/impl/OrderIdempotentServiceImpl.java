package com.macro.mall.portal.service.impl;

import com.macro.mall.portal.service.OrderIdempotentService;
import lombok.extern.slf4j.Slf4j;
import org.redisson.api.RBucket;
import org.redisson.api.RScript;
import org.redisson.api.RedissonClient;
import org.redisson.client.codec.StringCodec;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * 下单幂等令牌实现（债务23）。Redis + Lua 保证高并发下的原子认领，杜绝重复下单。
 */
@Service
@Slf4j
public class OrderIdempotentServiceImpl implements OrderIdempotentService {

    /** 令牌有效期（秒）：覆盖"用户慢慢填单 / 网络重传"窗口 */
    private static final long TTL_SECONDS = 900L;

    /**
     * 认领：读值 → 判定 → 改状态，三步必须在一次原子调用内完成，
     * 否则并发下两个同 token 请求可能都读到 "0" 而双双放行（幂等失效）。
     * 返回：-1 无效/过期；-2 处理中；0 认领成功；>0 已完成(orderId)。
     */
    private static final String CLAIM_LUA =
            "local v = redis.call('GET', KEYS[1]) \n" +
            "if not v then return -1 end \n" +
            "if v == '0' then redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2]) return 0 end \n" +
            "if v == 'P' then return -2 end \n" +
            "return tonumber(v)";

    /** 完成：回填订单号，之后同 token 一律返回该单。 */
    private static final String FINISH_LUA =
            "redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2]) \n" +
            "return 1";

    /** 回退：仅把处理中(P)置回未使用(0)，绝不覆盖已完成状态。 */
    private static final String RELEASE_LUA =
            "if redis.call('GET', KEYS[1]) == 'P' then \n" +
            "  redis.call('SET', KEYS[1], '0', 'EX', ARGV[1]) \n" +
            "  return 1 \n" +
            "end \n" +
            "return 0";

    @Autowired
    private RedissonClient redisson;

    private String key(Long memberId, String token) {
        return "idem:order:" + memberId + ":" + token;
    }

    @Override
    public String generate(Long memberId) {
        String token = UUID.randomUUID().toString();
        // 服务端生成，前端不可自造；key 含 memberId，杜绝跨用户重放
        redisson.getBucket(key(memberId, token), StringCodec.INSTANCE)
                .set("0", TTL_SECONDS, TimeUnit.SECONDS);
        return token;
    }

    @Override
    public Long claim(Long memberId, String token) {
        RScript script = redisson.getScript(StringCodec.INSTANCE);
        return script.eval(
                RScript.Mode.READ_WRITE,
                CLAIM_LUA,
                RScript.ReturnType.INTEGER,
                Collections.singletonList((Object) key(memberId, token)),
                "P", String.valueOf(TTL_SECONDS));
    }

    @Override
    public void finish(Long memberId, String token, Long orderId) {
        RScript script = redisson.getScript(StringCodec.INSTANCE);
        script.eval(
                RScript.Mode.READ_WRITE,
                FINISH_LUA,
                RScript.ReturnType.INTEGER,
                Collections.singletonList((Object) key(memberId, token)),
                String.valueOf(orderId), String.valueOf(TTL_SECONDS));
    }

    @Override
    public void release(Long memberId, String token) {
        RScript script = redisson.getScript(StringCodec.INSTANCE);
        script.eval(
                RScript.Mode.READ_WRITE,
                RELEASE_LUA,
                RScript.ReturnType.INTEGER,
                Collections.singletonList((Object) key(memberId, token)),
                String.valueOf(TTL_SECONDS));
    }
}
