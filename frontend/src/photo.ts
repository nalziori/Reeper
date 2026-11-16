// 휴대전화 원본 사진은 서버 한도(약 4MB)를 넘기 쉽다. 긴 변을 줄이고 JPEG로 바꿔 보낸다.
// 사진은 이 브라우저에서 줄이기만 하고 따로 보관하지 않는다.
const MAX_CHARS = 5_000_000 // 서버 agent.MAX_IMAGE(5,500,000자)보다 여유 있게
const STEPS: [number, number][] = [[2000, 0.85], [1600, 0.8], [1200, 0.75]]

export async function shrinkPhoto(file: File): Promise<string> {
  let bitmap: ImageBitmap
  try {
    // 파일을 메모리로 읽은 뒤 그린다. 형식이 틀린 파일은 여기서 걸러진다.
    const bytes = new Blob([await file.arrayBuffer()], { type: file.type })
    bitmap = await createImageBitmap(bytes)
  } catch {
    throw new Error('이 사진 형식은 읽지 못해요. JPG나 PNG 사진을 올려 주세요')
  }
  try {
    for (const [side, quality] of STEPS) {
      const scale = Math.min(1, side / Math.max(bitmap.width, bitmap.height))
      const canvas = document.createElement('canvas')
      canvas.width = Math.round(bitmap.width * scale)
      canvas.height = Math.round(bitmap.height * scale)
      canvas.getContext('2d')?.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
      const url = canvas.toDataURL('image/jpeg', quality)
      if (url.length <= MAX_CHARS) return url
    }
  } finally {
    bitmap.close()
  }
  throw new Error('사진이 너무 커요. 더 작은 사진을 올려 주세요')
}
