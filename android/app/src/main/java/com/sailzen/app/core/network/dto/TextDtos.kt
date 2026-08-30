package com.sailzen.app.core.network.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

/**
 * 文本阅读模块 DTOs，与服务端 sail_server.application.dto.text 对齐。
 */

@Serializable
data class WorkDto(
    val id: Int,
    val slug: String,
    val title: String,
    @SerialName("original_title") val originalTitle: String? = null,
    val author: String? = null,
    @SerialName("language_primary") val languagePrimary: String = "zh",
    @SerialName("work_type") val workType: String = "web_novel",
    val status: String = "ongoing",
    val synopsis: String? = null,
    @SerialName("meta_data") val metaData: Map<String, JsonElement?> = emptyMap(),
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
    @SerialName("word_count") val wordCount: Int? = null,
    @SerialName("chapter_count") val chapterCount: Int = 0,
    @SerialName("total_chars") val totalChars: Int = 0,
)

@Serializable
data class EditionDto(
    val id: Int,
    @SerialName("work_id") val workId: Int,
    @SerialName("edition_name") val editionName: String? = null,
    val language: String = "zh",
    @SerialName("source_format") val sourceFormat: String = "txt",
    val canonical: Boolean = false,
    val description: String? = null,
    @SerialName("source_path") val sourcePath: String? = null,
    @SerialName("source_checksum") val sourceChecksum: String? = null,
    @SerialName("ingest_version") val ingestVersion: Int = 1,
    @SerialName("word_count") val wordCount: Int? = null,
    @SerialName("char_count") val charCount: Int? = null,
    val status: String = "draft",
    @SerialName("meta_data") val metaData: Map<String, JsonElement?> = emptyMap(),
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
)

@Serializable
data class ChapterListItemDto(
    val id: Int,
    @SerialName("sort_index") val sortIndex: Int,
    val label: String,
    val title: String,
    @SerialName("char_count") val charCount: Int? = null,
    val path: String,
)

@Serializable
data class DocumentNodeDto(
    val id: Int,
    @SerialName("edition_id") val editionId: Int,
    @SerialName("node_type") val nodeType: String = "chapter",
    val title: String,
    @SerialName("raw_text") val rawText: String? = null,
    val path: String? = null,
    @SerialName("sort_index") val sortIndex: Int = 0,
    val level: Int = 1,
    @SerialName("parent_id") val parentId: Int? = null,
    @SerialName("word_count") val wordCount: Int? = null,
    @SerialName("char_count") val charCount: Int? = null,
    @SerialName("meta_data") val metaData: Map<String, JsonElement?> = emptyMap(),
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
)

@Serializable
data class NoteItemDto(
    val id: Int,
    val category: String,
    @SerialName("setting_file") val settingFile: String,
    @SerialName("work_id") val workId: Int? = null,
    @SerialName("edition_id") val editionId: Int? = null,
    val title: String? = null,
    val slug: String? = null,
    @SerialName("meta_data") val metaData: Map<String, JsonElement?> = emptyMap(),
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
)

@Serializable
data class NoteItemContentResponse(
    val id: Int,
    @SerialName("setting_file") val settingFile: String,
    val content: String,
)

@Serializable
data class NoteItemListResponse(
    val notes: List<NoteItemDto> = emptyList(),
    val total: Int = 0,
)

@Serializable
data class NoteItemCreateRequest(
    val category: String,
    @SerialName("setting_file") val settingFile: String? = null,
    @SerialName("work_id") val workId: Int? = null,
    @SerialName("edition_id") val editionId: Int? = null,
    val title: String? = null,
    val slug: String? = null,
    val content: String? = null,
    @SerialName("node_id") val nodeId: Int? = null,
    @SerialName("start_offset") val startOffset: Int? = null,
    @SerialName("end_offset") val endOffset: Int? = null,
    @SerialName("selected_text") val selectedText: String? = null,
    val color: String? = null,
    @SerialName("meta_data") val metaData: Map<String, JsonElement?> = emptyMap(),
)
