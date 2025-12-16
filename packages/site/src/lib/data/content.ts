/**
 * @file content.ts
 * @brief The Content Data API
 * @author sailing-innocent
 * @date 2025-01-31
 */

/*
"id": 119,
"title": "第五章",
"book_id": 2,
"content_node_id": -1,
"ctime": 1749346520,
"mtime": 1749346520,
"order": 4,
"content": "第五章内容",
*/

export class Chapter {
  id?: number = -1
  title?: string = ''
  book_id?: number = -1
  content_node_id?: number = -1
  ctime?: number = 0
  mtime?: number = 0
  order?: number = -1
  content?: string = ''
}

export interface BookInfo {
  id: number
  title: string
}

export interface Book {
  id: number
  title: string
  author: string
  chapters: number[]
}
