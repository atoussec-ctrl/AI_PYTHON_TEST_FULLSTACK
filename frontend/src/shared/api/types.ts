import type { components } from './schema'

type ApiSchemas = components['schemas']

export type Attachment = ApiSchemas['Attachment']
export type AttachmentKind = Attachment['kind']
export type Book = ApiSchemas['Book']
export type ChatMessage = ApiSchemas['ChatMessage']
export type ChatSession = ApiSchemas['ChatSession']
export type CreateBookInput = ApiSchemas['CreateBookRequest']
export type ImportBookResponse = ApiSchemas['ImportBookResponse']
export type SemanticSearchResult = ApiSchemas['SemanticSearchResponse']['results'][number]
export type SendMessageResponse = ApiSchemas['SendMessageResponse']
export type ThinkingMode = NonNullable<ChatMessage['thinking_mode']>

// The API makes thinking_mode optional and defaults it server-side. The UI
// deliberately requires an explicit choice so its state and rendered badge
// cannot silently diverge from the request it sent.
export type SendMessageInput = ApiSchemas['SendMessageRequest'] & {
  thinking_mode: ThinkingMode
}
