import { expect, test } from '@playwright/test'

test('browser, Vite proxy and Flask persist a chat turn and a book', async ({
  page,
  request,
}, testInfo) => {
  const runToken = `${Date.now().toString(36)}-${testInfo.retry}`
  const question = `E2E ${runToken}: como criar uma lista?`
  const bookTitle = `Teste Full Stack ${runToken}`

  const healthResponse = await request.get('/api/v1/health')
  expect(healthResponse.ok()).toBeTruthy()
  const health = await healthResponse.json()
  expect(health.request_id).toBe(healthResponse.headers()['x-request-id'])

  await page.goto('/')
  await expect(page.getByText('MindSight AI')).toBeVisible()

  await page.locator('input[type="file"]').setInputFiles({
    name: 'contexto.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('contexto persistido no envio multipart atomico'),
  })
  await expect(page.getByText('contexto.txt')).toBeVisible()
  await page.getByPlaceholder('Pergunte alguma coisa').fill(question)
  await page.getByRole('button', { name: 'Enviar mensagem' }).click()

  await expect(page.getByText(/Analisei os anexos enviados/)).toBeVisible()
  const sessionsResponse = await request.get('/api/v1/chat/sessions')
  expect(sessionsResponse.ok()).toBeTruthy()
  const sessions = await sessionsResponse.json()
  const session = sessions.find(
    (candidate: { title: string }) => candidate.title === question.slice(0, 54),
  )
  expect(session).toBeDefined()
  const messagesResponse = await request.get(
    `/api/v1/chat/sessions/${session.id}/messages`,
  )
  expect(messagesResponse.ok()).toBeTruthy()
  const messages = await messagesResponse.json()
  expect(messages[0].attachments).toHaveLength(1)
  expect(messages[0].attachments[0].filename).toBe('contexto.txt')

  await page.getByRole('button', { name: 'Biblioteca' }).click()
  await page.getByLabel('Título').fill(bookTitle)
  await page.getByRole('textbox', { name: 'Autor', exact: true }).fill('Equipe MindSight')
  await page.getByLabel('Ano de publicação').fill('2026')
  await page.getByLabel('Resumo').fill('Livro persistido pelo smoke test real.')
  await page.getByRole('button', { name: 'Cadastrar livro' }).click()

  await expect(page.getByText(bookTitle)).toBeVisible()
  const booksResponse = await request.get(`/api/v1/books?q=${encodeURIComponent(bookTitle)}`)
  expect(booksResponse.ok()).toBeTruthy()
  const books = await booksResponse.json()
  const book = books.find((candidate: { title: string }) => candidate.title === bookTitle)
  expect(book).toMatchObject({
    title: bookTitle,
    author: 'Equipe MindSight',
    publication_year: 2026,
  })
})
