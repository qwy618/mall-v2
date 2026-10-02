package com.macro.mall.admin.component;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

@Component
public class JwtTokenUtil {
    @Value("${jwt.secret}")
    private String secret;

    @Value("${jwt.expiration}")
    private Long expiration;
    private SecretKey getSecretKey() {
        return Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    }
    public String generateToken(String username) {
        Date now = new Date();
        Date exp = new Date(now.getTime() + expiration * 1000);
        return Jwts.builder()
                .subject(username)
                .issuedAt(now)
                .expiration(exp)
                .signWith(getSecretKey())
                .compact();
    }
    public String getUsernameFromToken(String token) {
        return parseClaims(token).getSubject();
    }

    public boolean isTokenExpired(String token) {
        return parseClaims(token).getExpiration().before(new Date());
    }

    /** 校验：能解析 + 用户名匹配 + 未过期 */
    public boolean validateToken(String token, String username) {
        try {
            final String tkUsername = getUsernameFromToken(token);
            return tkUsername.equals(username) && !isTokenExpired(token);
        } catch (Exception e) {
            return false;   // 过期/签名错/格式错 一律视为无效
        }
    }

    private Claims parseClaims(String token) {
        return Jwts.parser()
                .verifyWith(getSecretKey())        // ⚠️ 0.12 新写法
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }
}
