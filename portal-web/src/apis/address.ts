import request from '@/utils/request'
import type { Address } from '@/types/order'

// 收货地址列表
export function listAddresses() {
  return request<Address[]>({
    url: '/member/address/list',
    method: 'get',
  })
}

// 新增地址
export function addAddress(address: Address) {
  return request<null>({
    url: '/member/address/add',
    method: 'post',
    data: address,
  })
}

// 修改地址
export function updateAddress(address: Address) {
  return request<null>({
    url: '/member/address/update',
    method: 'post',
    data: address,
  })
}

// 删除地址
export function deleteAddress(id: number) {
  return request<null>({
    url: '/member/address/delete',
    method: 'post',
    params: { id },
  })
}

// 设为默认地址
export function setDefaultAddress(id: number) {
  return request<null>({
    url: '/member/address/setDefault',
    method: 'post',
    params: { id },
  })
}
