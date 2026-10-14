import React, { useMemo } from 'react'

export interface MarkdownRendererProps {
  content: string
  className?: string
  onCitationClick?: (refNumber: number) => void
}

/**
 * Safely parse inline markdown tokens: bold, italic, code, citation references [1], and plain text.
 */
function renderInlineContent(
  text: string,
  onCitationClick?: (refNumber: number) => void
): React.ReactNode[] {
  // Regex to match code blocks, bold, italic, and citation references [1]
  const inlineRegex =
    /(`[^`]+`)|(\*\*[^*]+\*\*)|(__[^_]+__)|(\*[^*]+\*)|(_[^_]+_)|(\[\d+\])/g

  const nodes: React.ReactNode[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = inlineRegex.exec(text)) !== null) {
    // Add text preceding match
    if (match.index > lastIndex) {
      nodes.push(text.substring(lastIndex, match.index))
    }

    const matchedStr = match[0]

    if (matchedStr.startsWith('`') && matchedStr.endsWith('`')) {
      // Inline code
      const code = matchedStr.slice(1, -1)
      nodes.push(
        <code
          key={`code-${match.index}`}
          className="px-1.5 py-0.5 rounded bg-surface-muted dark:bg-dark-muted font-mono text-[11px] sm:text-xs text-brand-700 dark:text-brand-300 border border-surface-border-subtle dark:border-dark-border-subtle break-all"
        >
          {code}
        </code>
      )
    } else if (
      (matchedStr.startsWith('**') && matchedStr.endsWith('**')) ||
      (matchedStr.startsWith('__') && matchedStr.endsWith('__'))
    ) {
      // Bold
      const boldText = matchedStr.slice(2, -2)
      nodes.push(
        <strong
          key={`bold-${match.index}`}
          className="font-bold text-surface-text dark:text-dark-text"
        >
          {renderInlineContent(boldText, onCitationClick)}
        </strong>
      )
    } else if (
      (matchedStr.startsWith('*') && matchedStr.endsWith('*')) ||
      (matchedStr.startsWith('_') && matchedStr.endsWith('_'))
    ) {
      // Italic
      const italicText = matchedStr.slice(1, -1)
      nodes.push(
        <em key={`italic-${match.index}`} className="italic">
          {renderInlineContent(italicText, onCitationClick)}
        </em>
      )
    } else if (matchedStr.startsWith('[') && matchedStr.endsWith(']')) {
      // Citation reference e.g. [1]
      const refNum = parseInt(matchedStr.slice(1, -1), 10)
      if (!isNaN(refNum)) {
        nodes.push(
          <button
            key={`cite-${match.index}`}
            type="button"
            onClick={() => onCitationClick?.(refNum)}
            className="inline-flex items-center justify-center px-1 py-0.2 rounded text-[10px] font-mono font-bold text-brand-700 dark:text-brand-300 hover:text-white bg-brand-50 hover:bg-brand-600 dark:bg-brand-950/60 dark:hover:bg-brand-500 border border-brand-200 dark:border-brand-800 transition-colors mx-0.5 align-baseline cursor-pointer"
            title={`View Source Citation [${refNum}]`}
          >
            [{refNum}]
          </button>
        )
      } else {
        nodes.push(matchedStr)
      }
    } else {
      nodes.push(matchedStr)
    }

    lastIndex = match.index + matchedStr.length
  }

  if (lastIndex < text.length) {
    nodes.push(text.substring(lastIndex))
  }

  return nodes
}

type Block =
  | { type: 'code'; language?: string; code: string }
  | { type: 'heading'; level: number; text: string }
  | { type: 'blockquote'; lines: string[] }
  | { type: 'ul'; items: string[] }
  | { type: 'ol'; items: string[] }
  | { type: 'paragraph'; lines: string[] }

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
  className = '',
  onCitationClick,
}) => {
  const blocks = useMemo(() => {
    if (!content) return []

    const lines = content.split('\n')
    const parsedBlocks: Block[] = []
    let i = 0

    while (i < lines.length) {
      const line = lines[i]

      // 1. Fenced Code Block
      if (line.trim().startsWith('```')) {
        const lang = line.trim().slice(3).trim()
        const codeLines: string[] = []
        i++
        while (i < lines.length && !lines[i].trim().startsWith('```')) {
          codeLines.push(lines[i])
          i++
        }
        if (i < lines.length) i++ // skip ending ```
        parsedBlocks.push({
          type: 'code',
          language: lang || undefined,
          code: codeLines.join('\n'),
        })
        continue
      }

      // 2. Headings: #, ##, ###
      const headingMatch = line.match(/^(#{1,6})\s+(.*)$/)
      if (headingMatch) {
        parsedBlocks.push({
          type: 'heading',
          level: headingMatch[1].length,
          text: headingMatch[2].trim(),
        })
        i++
        continue
      }

      // 3. Blockquote
      if (line.trim().startsWith('>')) {
        const quoteLines: string[] = [line.trim().replace(/^>\s?/, '')]
        i++
        while (i < lines.length && lines[i].trim().startsWith('>')) {
          quoteLines.push(lines[i].trim().replace(/^>\s?/, ''))
          i++
        }
        parsedBlocks.push({
          type: 'blockquote',
          lines: quoteLines,
        })
        continue
      }

      // 4. Unordered List (- or *)
      if (line.match(/^(\s*[-*]\s+)/)) {
        const listItems: string[] = [line.replace(/^\s*[-*]\s+/, '')]
        i++
        while (i < lines.length && lines[i].match(/^(\s*[-*]\s+)/)) {
          listItems.push(lines[i].replace(/^\s*[-*]\s+/, ''))
          i++
        }
        parsedBlocks.push({
          type: 'ul',
          items: listItems,
        })
        continue
      }

      // 5. Ordered List (1. 2.)
      if (line.match(/^(\s*\d+\.\s+)/)) {
        const listItems: string[] = [line.replace(/^\s*\d+\.\s+/, '')]
        i++
        while (i < lines.length && lines[i].match(/^(\s*\d+\.\s+)/)) {
          listItems.push(lines[i].replace(/^\s*\d+\.\s+/, ''))
          i++
        }
        parsedBlocks.push({
          type: 'ol',
          items: listItems,
        })
        continue
      }

      // 6. Empty Line
      if (!line.trim()) {
        i++
        continue
      }

      // 7. Paragraph
      const pLines: string[] = [line]
      i++
      while (
        i < lines.length &&
        lines[i].trim() &&
        !lines[i].trim().startsWith('```') &&
        !lines[i].match(/^(#{1,6})\s+/) &&
        !lines[i].trim().startsWith('>') &&
        !lines[i].match(/^(\s*[-*]\s+)/) &&
        !lines[i].match(/^(\s*\d+\.\s+)/)
      ) {
        pLines.push(lines[i])
        i++
      }
      parsedBlocks.push({
        type: 'paragraph',
        lines: pLines,
      })
    }

    return parsedBlocks
  }, [content])

  return (
    <div
      className={`space-y-2.5 wrap-break-word overflow-hidden text-surface-text dark:text-dark-text ${className}`}
      style={{ overflowWrap: 'anywhere' }}
    >
      {blocks.map((block, idx) => {
        switch (block.type) {
          case 'code':
            return (
              <div
                key={idx}
                className="my-2.5 rounded-lg overflow-hidden border border-surface-border dark:border-dark-border bg-stone-900 text-stone-100 text-xs shadow-xs"
              >
                {block.language && (
                  <div className="px-3 py-1 bg-stone-800 text-[10px] font-mono text-stone-400 uppercase tracking-wider border-b border-stone-800">
                    {block.language}
                  </div>
                )}
                <pre className="p-3 overflow-x-auto font-mono text-xs leading-relaxed">
                  <code>{block.code}</code>
                </pre>
              </div>
            )

          case 'heading': {
            const headingContent = renderInlineContent(block.text, onCitationClick)
            if (block.level === 1) {
              return (
                <h1
                  key={idx}
                  className="text-base sm:text-lg font-extrabold tracking-tight mt-3 mb-1 text-surface-text dark:text-dark-text border-b border-surface-border-subtle dark:border-dark-border-subtle pb-1"
                >
                  {headingContent}
                </h1>
              )
            }
            if (block.level === 2) {
              return (
                <h2
                  key={idx}
                  className="text-sm sm:text-base font-bold tracking-tight mt-2.5 mb-1 text-surface-text dark:text-dark-text"
                >
                  {headingContent}
                </h2>
              )
            }
            return (
              <h3
                key={idx}
                className="text-xs sm:text-sm font-semibold mt-2 mb-0.5 text-surface-text dark:text-dark-text"
              >
                {headingContent}
              </h3>
            )
          }

          case 'blockquote':
            return (
              <blockquote
                key={idx}
                className="pl-3 py-1 my-1.5 border-l-3 border-brand-500 text-surface-text-muted dark:text-dark-text-muted italic text-xs leading-relaxed bg-surface-muted/30 dark:bg-dark-muted/30 rounded-r"
              >
                {block.lines.map((l, lIdx) => (
                  <p key={lIdx}>{renderInlineContent(l, onCitationClick)}</p>
                ))}
              </blockquote>
            )

          case 'ul':
            return (
              <ul
                key={idx}
                className="list-disc pl-5 my-1.5 space-y-1 text-xs sm:text-sm leading-relaxed"
              >
                {block.items.map((item, itemIdx) => (
                  <li key={itemIdx}>{renderInlineContent(item, onCitationClick)}</li>
                ))}
              </ul>
            )

          case 'ol':
            return (
              <ol
                key={idx}
                className="list-decimal pl-5 my-1.5 space-y-1 text-xs sm:text-sm leading-relaxed"
              >
                {block.items.map((item, itemIdx) => (
                  <li key={itemIdx}>{renderInlineContent(item, onCitationClick)}</li>
                ))}
              </ol>
            )

          case 'paragraph':
            return (
              <p key={idx} className="leading-relaxed text-xs sm:text-sm">
                {block.lines.map((l, lIdx) => (
                  <React.Fragment key={lIdx}>
                    {renderInlineContent(l, onCitationClick)}
                    {lIdx < block.lines.length - 1 && <br />}
                  </React.Fragment>
                ))}
              </p>
            )

          default:
            return null
        }
      })}
    </div>
  )
}
