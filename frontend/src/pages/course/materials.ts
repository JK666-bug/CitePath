import type { Material } from './types'

export type NumberedMaterial = Material & {
  displayNumber: number
}

export function numberMaterials(
  materials: readonly Material[],
): NumberedMaterial[] {
  // 当前后端按入库时生成的文件 ID 返回上传顺序。
  // 复制后排序，避免修改 React 状态中的原始数组。
  const ordered = [...materials].sort(
    (first, second) => first.id - second.id,
  )

  // 显示序号随当前课程资料更新，真实 ID 继续用于接口和来源关联。
  return ordered.map((material, index) => ({
    ...material,
    displayNumber: index + 1,
  }))
}
