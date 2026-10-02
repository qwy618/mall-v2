package com.macro.mall.admin.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.macro.mall.admin.dto.BrandParam;
import com.macro.mall.mbg.model.Brand;
import jakarta.validation.Valid;
import org.springframework.stereotype.Service;


public interface BrandService {
    public IPage<Brand> list(int pageNum, int pageSize);

    Brand getItem(Long id);

    Long create(BrandParam brandParam);

    Long delete(Long id);

    Long update(Long id, @Valid BrandParam brandParam);
}
