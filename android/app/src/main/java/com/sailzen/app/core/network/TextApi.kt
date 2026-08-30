package com.sailzen.app.core.network

import com.sailzen.app.core.network.dto.ChapterListItemDto
import com.sailzen.app.core.network.dto.DocumentNodeDto
import com.sailzen.app.core.network.dto.EditionDto
import com.sailzen.app.core.network.dto.NoteItemContentResponse
import com.sailzen.app.core.network.dto.NoteItemCreateRequest
import com.sailzen.app.core.network.dto.NoteItemDto
import com.sailzen.app.core.network.dto.NoteItemListResponse
import com.sailzen.app.core.network.dto.WorkDto
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * 文本阅读 REST API（前缀 /api/v1/text）。
 */
interface TextApi {

    // ---------------- Work ----------------

    @GET("api/v1/text/work")
    suspend fun works(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 20,
    ): List<WorkDto>

    // ---------------- Edition ----------------

    @GET("api/v1/text/edition/work/{work_id}")
    suspend fun editionsByWork(
        @Path("work_id") workId: Int,
    ): List<EditionDto>

    @GET("api/v1/text/edition/{edition_id}/chapters")
    suspend fun chapterList(
        @Path("edition_id") editionId: Int,
    ): List<ChapterListItemDto>

    @GET("api/v1/text/edition/{edition_id}/chapter/{chapter_index}")
    suspend fun chapterContent(
        @Path("edition_id") editionId: Int,
        @Path("chapter_index") chapterIndex: Int,
    ): DocumentNodeDto

    // ---------------- NoteItem ----------------

    @GET("api/v1/text/note")
    suspend fun notes(
        @Query("category") category: String? = null,
        @Query("work_id") workId: Int? = null,
        @Query("edition_id") editionId: Int? = null,
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 100,
    ): NoteItemListResponse

    @POST("api/v1/text/note")
    suspend fun createNote(@Body body: NoteItemCreateRequest): NoteItemDto

    @DELETE("api/v1/text/note/{note_id}")
    suspend fun deleteNote(@Path("note_id") noteId: Int): NoteItemDto

    @GET("api/v1/text/note/{note_id}/content")
    suspend fun noteContent(@Path("note_id") noteId: Int): NoteItemContentResponse
}
