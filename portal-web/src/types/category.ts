export interface CategoryNode {
  id: number
  name: string
  icon?: string
  parentId: number | null
  children: CategoryNode[]
}
