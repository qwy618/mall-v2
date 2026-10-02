package com.macro.mall.common;

import com.baomidou.mybatisplus.core.metadata.IPage;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.util.List;

@Data
@AllArgsConstructor
@NoArgsConstructor
public class CommonPage<T> {
    private Integer pageNum;
    private Integer pageSize;
    private Integer totalPage;
    private Long total;          // ← 改 Long，MP 的 getTotal() 返回 long，用 Integer 强转会溢出
    private List<T> list;

    public static <T> CommonPage<T> restPage(IPage<T> page) {
        CommonPage<T> result = new CommonPage<>();
        result.setPageNum((int) page.getCurrent());
        result.setPageSize((int) page.getSize());
        result.setTotal(page.getTotal());
        result.setTotalPage(calcTotalPage(page.getTotal(), (int) page.getSize()));
        result.setList(page.getRecords());
        return result;
    }

    private static Integer calcTotalPage(Long total, Integer pageSize) {
        if (pageSize == null || pageSize <= 0) {
            return 0;                      // 防除零，否则 pageSize=0 直接 ArithmeticException
        }
        return (int) ((total + pageSize - 1) / pageSize);
    }
}
