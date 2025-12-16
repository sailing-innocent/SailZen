SELECT chapter.id, chapter.title FROM chapter 
INNER JOIN book ON chapter.book_id=book.id
WHERE book.id=1