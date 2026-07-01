/**
 * 复制文本到剪贴板，支持在非安全上下文（如 http + IP）下的 fallback 回退
 */
export async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch (err) {
      console.warn('navigator.clipboard.writeText failed, trying fallback:', err)
    }
  }

  // Fallback using document.execCommand('copy')
  const textArea = document.createElement('textarea')
  textArea.value = text
  
  // Make the textarea out of screen and non-intrusive
  textArea.style.position = 'fixed'
  textArea.style.top = '-9999px'
  textArea.style.left = '-9999px'
  textArea.style.opacity = '0'
  
  document.body.appendChild(textArea)
  textArea.focus()
  textArea.select()

  try {
    const successful = document.execCommand('copy')
    if (!successful) {
      throw new Error('Copy command failed')
    }
  } catch (err) {
    throw err
  } finally {
    document.body.removeChild(textArea)
  }
}
