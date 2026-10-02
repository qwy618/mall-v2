// 环境声明：vite.config.ts 使用了 node:url，但项目未安装 @types/node（保持依赖精简，
// 且沙箱环境无法联网安装）。声明最小可用的 node:url 类型即可让 vue-tsc 类型检查通过；
// 运行时 vite 本身运行在 Node 环境中，node:url 是真实可用的，不受影响。
declare module 'node:url' {
  export function fileURLToPath(url: string | URL): string
  export class URL {
    constructor(input: string, base?: string | URL)
    pathname: string
    href: string
  }
}
