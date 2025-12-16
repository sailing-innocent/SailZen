SELECT content_node.start, content_node.offset, content.data, content.size FROM chapter 
INNER JOIN book ON chapter.book_id=book.id
INNER JOIN content_node ON content_node.id=chapter.content_node_id 
INNER JOIN content ON content.id=content_node.content_id 
WHERE book.id=1 AND chapter.order=13;