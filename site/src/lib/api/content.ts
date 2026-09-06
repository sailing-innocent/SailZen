/**
 * @file content.ts
 * @brief The Content API
 * @author sailing-innocent
 * @date 2025-01-31
 */

import { Chapter, type Book, type BookInfo } from '@lib/data/content'
import { SERVER_URL, API_BASE } from './config'
const CONTENT_API_BASE = API_BASE + '/content'

const api_get_books = async (skip: number, limit: number): Promise<BookInfo[]> => {
  const response = await fetch(`${SERVER_URL}/${CONTENT_API_BASE}/books/?skip=${skip}&limit=${limit}`)
  return response.json()
}

const api_get_book = async (id: number): Promise<Book> => {
  const response = await fetch(`${SERVER_URL}/${CONTENT_API_BASE}/book/${id}`)
  return response.json()
}

const api_get_chapter = async (id: number): Promise<Chapter> => {
  const response = await fetch(`${SERVER_URL}/${CONTENT_API_BASE}/chapter/${id}`)
  return response.json()
}

const api_get_book_chapter = async (bookId: number, chapterOrder: number): Promise<Chapter> => {
  const response = await fetch(`${SERVER_URL}/${CONTENT_API_BASE}/chapter/?book=${bookId}&order=${chapterOrder}`)
  return response.json()
}

export { api_get_books, api_get_book, api_get_chapter, api_get_book_chapter }
