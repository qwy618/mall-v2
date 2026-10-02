package com.macro.mall.admin.service.Impl;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.macro.mall.admin.dto.BrandParam;
import com.macro.mall.admin.service.BrandService;
import com.macro.mall.common.ResultCode;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.BrandMapper;
import com.macro.mall.mbg.model.Brand;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class BrandServiceImpl implements BrandService {
    @Autowired
    BrandMapper brandMapper;
    @Override
    public IPage<Brand> list(int pageNum, int pageSize) {
          //1.创建page对象
        IPage<Brand> page = new Page<>(pageNum, pageSize);
          //2.调用mapper方法查询
        IPage<Brand> brandIPage = brandMapper.selectPage(page, null);
        return brandIPage;
    }

    @Override
    public Brand getItem(Long id) {
        Brand brand = brandMapper.selectById(id);
        if(brand == null){
            throw new BusinessException(ResultCode.NOT_FOUND,"品牌不存在");
        }
        return brand;
    }

    @Override
    public Long create(BrandParam brandParam) {
        Brand brand = new Brand();
        BeanUtils.copyProperties(brandParam, brand);
        int insert = brandMapper.insert(brand);
        return brand.getId();
    }

    @Override
    public Long delete(Long id) {
        int rows = brandMapper.deleteById(id);
        return (long) rows;
    }

    @Override
    public Long update(Long id, BrandParam param) {
        Brand brand = new Brand();
        BeanUtils.copyProperties(param, brand);   // 只拷贝 Param 白名单字段
        brand.setId(id);
        // 不手动 set createTime/updateTime（交给 DB 默认值，阶段2 约定）
        return (long) brandMapper.updateById(brand);
    }
}
