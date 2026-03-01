# -*- coding: utf-8 -*-
# @file necessity.py
# @brief The Necessity Controller
# @author sailing-innocent
# @date 2026-02-01
# @version 1.0
# ---------------------------------

from __future__ import annotations
from litestar import Controller, delete, get, post, put, Request
from litestar.exceptions import HTTPException
from sqlalchemy.orm import Session
from typing import Generator, Optional

from sail_server.application.dto.necessity import (
    ResidenceCreateRequest,
    ResidenceUpdateRequest,
    ResidenceResponse,
    ContainerCreateRequest,
    ContainerUpdateRequest,
    ContainerResponse,
    ItemCategoryCreateRequest,
    ItemCategoryUpdateRequest,
    ItemCategoryResponse,
    ItemCreateRequest,
    ItemUpdateRequest,
    ItemResponse,
    InventoryCreateRequest,
    InventoryUpdateRequest,
    InventoryResponse,
    JourneyCreateRequest,
    JourneyUpdateRequest,
    JourneyResponse,
    JourneyItemCreateRequest,
    JourneyItemResponse,
    ReplenishmentCreateRequest,
    ReplenishmentResponse,
)

from sail_server.model.necessity.residence import (
    create_residence_impl,
    read_residence_impl,
    read_residences_impl,
    update_residence_impl,
    delete_residence_impl,
    get_portable_residence_impl,
)

from sail_server.model.necessity.container import (
    create_container_impl,
    read_container_impl,
    read_containers_impl,
    read_containers_by_residence_impl,
    update_container_impl,
    delete_container_impl,
    get_container_tree_impl,
)

from sail_server.model.necessity.category import (
    create_category_impl,
    read_category_impl,
    read_categories_impl,
    update_category_impl,
    delete_category_impl,
    get_category_tree_impl,
    seed_default_categories_impl,
)

from sail_server.model.necessity.item import (
    create_item_impl,
    read_item_impl,
    read_items_impl,
    read_items_paginated_impl,
    update_item_impl,
    delete_item_impl,
    search_items_impl,
    get_expiring_items_impl,
    get_portable_items_impl,
)

from sail_server.model.necessity.inventory import (
    create_inventory_impl,
    read_inventory_impl,
    read_inventories_impl,
    read_inventories_by_residence_impl,
    read_inventories_by_item_impl,
    update_inventory_impl,
    delete_inventory_impl,
    record_consumption_impl,
    record_replenishment_impl,
    transfer_inventory_impl,
    get_low_stock_impl,
    get_inventory_stats_impl,
)

from sail_server.model.necessity.journey import (
    create_journey_impl,
    read_journey_impl,
    read_journeys_impl,
    update_journey_impl,
    delete_journey_impl,
    start_journey_impl,
    complete_journey_impl,
    cancel_journey_impl,
    add_journey_item_impl,
    remove_journey_item_impl,
    pack_journey_item_impl,
    unpack_journey_item_impl,
)


# -------------
# Residence Controller
# -------------

class ResidenceController(Controller):
    path = "/residence"

    @get("/{residence_id:int}")
    async def get_residence(
        self,
        residence_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ResidenceResponse:
        """Get a residence by ID"""
        try:
            db = next(router_dependency)
            residence = read_residence_impl(db, residence_id)
            if residence is None:
                raise HTTPException(status_code=404, detail="Residence not found")
            return residence
        except HTTPException:
            raise
        except Exception as e:
            request.logger.error(f"Error getting residence: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @get()
    async def get_residences(
        self,
        router_dependency: Generator[Session, None, None],
        skip: int = 0,
        limit: int = -1,
        residence_type: Optional[int] = None,
    ) -> list[ResidenceResponse]:
        """Get all residences"""
        db = next(router_dependency)
        return read_residences_impl(db, skip, limit, residence_type)

    @post()
    async def create_residence(
        self,
        data: ResidenceCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ResidenceResponse:
        """Create a new residence"""
        db = next(router_dependency)
        if not data.name or not data.name.strip():
            raise HTTPException(status_code=400, detail="Residence name is required")
        residence = create_residence_impl(db, data)
        request.logger.info(f"Created residence: {residence}")
        return residence

    @put("/{residence_id:int}")
    async def update_residence(
        self,
        residence_id: int,
        data: ResidenceUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ResidenceResponse:
        """Update a residence"""
        db = next(router_dependency)
        residence = update_residence_impl(db, residence_id, data)
        if residence is None:
            raise HTTPException(status_code=404, detail="Residence not found")
        request.logger.info(f"Updated residence: {residence}")
        return residence

    @delete("/{residence_id:int}", status_code=200)
    async def delete_residence(
        self,
        residence_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """Delete a residence"""
        db = next(router_dependency)
        result = delete_residence_impl(db, residence_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Residence not found")
        request.logger.info(f"Deleted residence: {residence_id}")
        return {"id": residence_id, "status": "success", "message": "Residence deleted"}

    @get("/portable")
    async def get_portable_residence(
        self,
        router_dependency: Generator[Session, None, None],
    ) -> ResidenceResponse:
        """Get the portable (随身携带) residence"""
        db = next(router_dependency)
        residence = get_portable_residence_impl(db)
        if residence is None:
            raise HTTPException(status_code=404, detail="Portable residence not found")
        return residence

    @get("/{residence_id:int}/inventory")
    async def get_residence_inventory(
        self,
        residence_id: int,
        router_dependency: Generator[Session, None, None],
    ) -> list[InventoryResponse]:
        """Get all inventory in a residence"""
        db = next(router_dependency)
        return read_inventories_by_residence_impl(db, residence_id)

    @get("/{residence_id:int}/low-stock")
    async def get_residence_low_stock(
        self,
        residence_id: int,
        router_dependency: Generator[Session, None, None],
    ) -> list[InventoryResponse]:
        """Get low stock items in a residence"""
        db = next(router_dependency)
        return get_low_stock_impl(db, residence_id)


# -------------
# Container Controller
# -------------

class ContainerController(Controller):
    path = "/container"

    @get("/{container_id:int}")
    async def get_container(
        self,
        container_id: int,
        router_dependency: Generator[Session, None, None],
    ) -> ContainerResponse:
        """Get a container by ID"""
        db = next(router_dependency)
        container = read_container_impl(db, container_id)
        if container is None:
            raise HTTPException(status_code=404, detail="Container not found")
        return container

    @get()
    async def get_containers(
        self,
        router_dependency: Generator[Session, None, None],
        residence_id: Optional[int] = None,
        skip: int = 0,
        limit: int = -1,
    ) -> list[ContainerResponse]:
        """Get containers, optionally filtered by residence"""
        db = next(router_dependency)
        if residence_id:
            return read_containers_by_residence_impl(db, residence_id)
        return read_containers_impl(db, skip, limit)

    @post()
    async def create_container(
        self,
        data: ContainerCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ContainerResponse:
        """Create a new container"""
        db = next(router_dependency)
        if not data.name or not data.name.strip():
            raise HTTPException(status_code=400, detail="Container name is required")
        if data.residence_id <= 0:
            raise HTTPException(status_code=400, detail="Residence ID is required")
        container = create_container_impl(db, data)
        request.logger.info(f"Created container: {container}")
        return container

    @put("/{container_id:int}")
    async def update_container(
        self,
        container_id: int,
        data: ContainerUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ContainerResponse:
        """Update a container"""
        db = next(router_dependency)
        container = update_container_impl(db, container_id, data)
        if container is None:
            raise HTTPException(status_code=404, detail="Container not found")
        request.logger.info(f"Updated container: {container}")
        return container

    @delete("/{container_id:int}", status_code=200)
    async def delete_container(
        self,
        container_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """Delete a container"""
        db = next(router_dependency)
        result = delete_container_impl(db, container_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Container not found")
        request.logger.info(f"Deleted container: {container_id}")
        return {"id": container_id, "status": "success", "message": "Container deleted"}

    @get("/tree/{residence_id:int}")
    async def get_container_tree(
        self,
        residence_id: int,
        router_dependency: Generator[Session, None, None],
    ) -> list[dict]:
        """Get container tree for a residence"""
        db = next(router_dependency)
        return get_container_tree_impl(db, residence_id)


# -------------
# Category Controller
# -------------

class CategoryController(Controller):
    path = "/category"

    @get("/{category_id:int}")
    async def get_category(
        self,
        category_id: int,
        router_dependency: Generator[Session, None, None],
    ) -> ItemCategoryResponse:
        """Get a category by ID"""
        db = next(router_dependency)
        category = read_category_impl(db, category_id)
        if category is None:
            raise HTTPException(status_code=404, detail="Category not found")
        return category

    @get()
    async def get_categories(
        self,
        router_dependency: Generator[Session, None, None],
        skip: int = 0,
        limit: int = -1,
    ) -> list[ItemCategoryResponse]:
        """Get all categories"""
        db = next(router_dependency)
        return read_categories_impl(db, skip, limit)

    @post()
    async def create_category(
        self,
        data: ItemCategoryCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ItemCategoryResponse:
        """Create a new category"""
        db = next(router_dependency)
        if not data.name or not data.name.strip():
            raise HTTPException(status_code=400, detail="Category name is required")
        category = create_category_impl(db, data)
        request.logger.info(f"Created category: {category}")
        return category

    @put("/{category_id:int}")
    async def update_category(
        self,
        category_id: int,
        data: ItemCategoryUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ItemCategoryResponse:
        """Update a category"""
        db = next(router_dependency)
        category = update_category_impl(db, category_id, data)
        if category is None:
            raise HTTPException(status_code=404, detail="Category not found")
        request.logger.info(f"Updated category: {category}")
        return category

    @delete("/{category_id:int}", status_code=200)
    async def delete_category(
        self,
        category_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """Delete a category"""
        db = next(router_dependency)
        result = delete_category_impl(db, category_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Category not found")
        request.logger.info(f"Deleted category: {category_id}")
        return {"id": category_id, "status": "success", "message": "Category deleted"}

    @get("/tree")
    async def get_category_tree(
        self,
        router_dependency: Generator[Session, None, None],
    ) -> list[dict]:
        """Get category tree"""
        db = next(router_dependency)
        return get_category_tree_impl(db)

    @post("/seed")
    async def seed_categories(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> list[ItemCategoryResponse]:
        """Seed default categories"""
        db = next(router_dependency)
        categories = seed_default_categories_impl(db)
        request.logger.info(f"Seeded {len(categories)} categories")
        return categories


# -------------
# Item Controller
# -------------

class ItemController(Controller):
    path = "/item"

    @get("/{item_id:int}")
    async def get_item(
        self,
        item_id: int,
        router_dependency: Generator[Session, None, None],
    ) -> ItemResponse:
        """Get an item by ID"""
        db = next(router_dependency)
        item = read_item_impl(db, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        return item

    @get()
    async def get_items(
        self,
        router_dependency: Generator[Session, None, None],
        skip: int = 0,
        limit: int = -1,
        category_id: Optional[int] = None,
        item_type: Optional[int] = None,
        item_state: Optional[int] = None,
        tags: str = "",
    ) -> list[ItemResponse]:
        """Get items with optional filtering"""
        db = next(router_dependency)
        return read_items_impl(
            db, skip, limit,
            category_id=category_id,
            item_type=item_type,
            state=item_state,
            tags=tags if tags else None,
        )

    @get("/paginated/")
    async def get_items_paginated(
        self,
        router_dependency: Generator[Session, None, None],
        page: int = 1,
        page_size: int = 20,
        category_id: Optional[int] = None,
        item_type: Optional[int] = None,
        item_state: Optional[int] = None,
        tags: str = "",
        keyword: str = "",
        sort_by: str = "mtime",
        sort_order: str = "desc",
    ) -> dict:
        """Get items with pagination"""
        db = next(router_dependency)
        return read_items_paginated_impl(
            db,
            page=page,
            page_size=page_size,
            category_id=category_id,
            item_type=item_type,
            state=item_state,
            tags=tags if tags else None,
            keyword=keyword if keyword else None,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    @post()
    async def create_item(
        self,
        data: ItemCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ItemResponse:
        """Create a new item"""
        db = next(router_dependency)
        if not data.name or not data.name.strip():
            raise HTTPException(status_code=400, detail="Item name is required")
        item = create_item_impl(db, data)
        request.logger.info(f"Created item: {item}")
        return item

    @put("/{item_id:int}")
    async def update_item(
        self,
        item_id: int,
        data: ItemUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ItemResponse:
        """Update an item"""
        db = next(router_dependency)
        item = update_item_impl(db, item_id, data)
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        request.logger.info(f"Updated item: {item}")
        return item

    @delete("/{item_id:int}", status_code=200)
    async def delete_item(
        self,
        item_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """Delete an item"""
        db = next(router_dependency)
        result = delete_item_impl(db, item_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Item not found")
        request.logger.info(f"Deleted item: {item_id}")
        return {"id": item_id, "status": "success", "message": "Item deleted"}

    @get("/search/")
    async def search_items(
        self,
        router_dependency: Generator[Session, None, None],
        keyword: str = "",
        limit: int = 20,
    ) -> list[ItemResponse]:
        """Search items by keyword"""
        db = next(router_dependency)
        if not keyword:
            return []
        return search_items_impl(db, keyword, limit)

    @get("/expiring/")
    async def get_expiring_items(
        self,
        router_dependency: Generator[Session, None, None],
        days: int = 30,
    ) -> list[dict]:
        """Get items expiring within specified days"""
        db = next(router_dependency)
        return get_expiring_items_impl(db, days)

    @get("/portable/")
    async def get_portable_items(
        self,
        router_dependency: Generator[Session, None, None],
        min_portability: int = 4,
    ) -> list[ItemResponse]:
        """Get portable items for travel"""
        db = next(router_dependency)
        return get_portable_items_impl(db, min_portability)

    @get("/{item_id:int}/locations")
    async def get_item_locations(
        self,
        item_id: int,
        router_dependency: Generator[Session, None, None],
    ) -> list[InventoryResponse]:
        """Get all locations where an item is stored"""
        db = next(router_dependency)
        return read_inventories_by_item_impl(db, item_id)


# -------------
# Inventory Controller
# -------------

class InventoryController(Controller):
    path = "/inventory"

    @get("/{inventory_id:int}")
    async def get_inventory(
        self,
        inventory_id: int,
        router_dependency: Generator[Session, None, None],
    ) -> InventoryResponse:
        """Get an inventory record by ID"""
        db = next(router_dependency)
        inventory = read_inventory_impl(db, inventory_id)
        if inventory is None:
            raise HTTPException(status_code=404, detail="Inventory not found")
        return inventory

    @get()
    async def get_inventories(
        self,
        router_dependency: Generator[Session, None, None],
        skip: int = 0,
        limit: int = -1,
    ) -> list[InventoryResponse]:
        """Get all inventory records"""
        db = next(router_dependency)
        return read_inventories_impl(db, skip, limit)

    @post()
    async def create_inventory(
        self,
        data: InventoryCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> InventoryResponse:
        """Create a new inventory record"""
        db = next(router_dependency)
        if data.item_id <= 0:
            raise HTTPException(status_code=400, detail="Item ID is required")
        if data.residence_id <= 0:
            raise HTTPException(status_code=400, detail="Residence ID is required")
        inventory = create_inventory_impl(db, data)
        request.logger.info(f"Created inventory: {inventory}")
        return inventory

    @put("/{inventory_id:int}")
    async def update_inventory(
        self,
        inventory_id: int,
        data: InventoryUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> InventoryResponse:
        """Update an inventory record"""
        db = next(router_dependency)
        inventory = update_inventory_impl(db, inventory_id, data)
        if inventory is None:
            raise HTTPException(status_code=404, detail="Inventory not found")
        request.logger.info(f"Updated inventory: {inventory}")
        return inventory

    @delete("/{inventory_id:int}", status_code=200)
    async def delete_inventory(
        self,
        inventory_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """Delete an inventory record"""
        db = next(router_dependency)
        result = delete_inventory_impl(db, inventory_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Inventory not found")
        request.logger.info(f"Deleted inventory: {inventory_id}")
        return {"id": inventory_id, "status": "success", "message": "Inventory deleted"}

    @post("/{inventory_id:int}/consume")
    async def consume_inventory(
        self,
        inventory_id: int,
        data: dict,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> InventoryResponse:
        """Record consumption for an inventory"""
        db = next(router_dependency)
        try:
            quantity = data.get("quantity", "0")
            reason = data.get("reason", "")
            inventory = record_consumption_impl(db, inventory_id, quantity, reason)
            request.logger.info(f"Recorded consumption for inventory {inventory_id}")
            return inventory
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @post("/{inventory_id:int}/replenish")
    async def replenish_inventory(
        self,
        inventory_id: int,
        data: ReplenishmentCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> InventoryResponse:
        """Record replenishment for an inventory"""
        db = next(router_dependency)
        try:
            inventory = record_replenishment_impl(db, inventory_id, data)
            request.logger.info(f"Recorded replenishment for inventory {inventory_id}")
            return inventory
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @post("/transfer")
    async def transfer_inventory(
        self,
        data: dict,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> dict:
        """Transfer inventory between residences"""
        db = next(router_dependency)
        try:
            result = transfer_inventory_impl(
                db,
                item_id=data.get("item_id"),
                from_residence_id=data.get("from_residence_id"),
                to_residence_id=data.get("to_residence_id"),
                quantity=data.get("quantity", "1"),
                from_container_id=data.get("from_container_id"),
                to_container_id=data.get("to_container_id"),
            )
            request.logger.info(f"Transferred inventory: {result}")
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @get("/low-stock/")
    async def get_low_stock(
        self,
        router_dependency: Generator[Session, None, None],
        residence_id: Optional[int] = None,
    ) -> list[InventoryResponse]:
        """Get low stock inventory"""
        db = next(router_dependency)
        return get_low_stock_impl(db, residence_id)

    @get("/stats/")
    async def get_inventory_stats(
        self,
        router_dependency: Generator[Session, None, None],
        residence_id: Optional[int] = None,
    ) -> dict:
        """Get inventory statistics"""
        db = next(router_dependency)
        return get_inventory_stats_impl(db, residence_id)


# -------------
# Journey Controller
# -------------

class JourneyController(Controller):
    path = "/journey"

    @get("/{journey_id:int}")
    async def get_journey(
        self,
        journey_id: int,
        router_dependency: Generator[Session, None, None],
    ) -> JourneyResponse:
        """Get a journey by ID"""
        db = next(router_dependency)
        journey = read_journey_impl(db, journey_id, include_items=True)
        if journey is None:
            raise HTTPException(status_code=404, detail="Journey not found")
        return journey

    @get()
    async def get_journeys(
        self,
        router_dependency: Generator[Session, None, None],
        skip: int = 0,
        limit: int = -1,
        status: Optional[int] = None,
        from_residence_id: Optional[int] = None,
        to_residence_id: Optional[int] = None,
    ) -> list[JourneyResponse]:
        """Get journeys with optional filtering"""
        db = next(router_dependency)
        return read_journeys_impl(
            db, skip, limit,
            status=status,
            from_residence_id=from_residence_id,
            to_residence_id=to_residence_id,
        )

    @post()
    async def create_journey(
        self,
        data: JourneyCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> JourneyResponse:
        """Create a new journey"""
        db = next(router_dependency)
        if data.from_residence_id <= 0:
            raise HTTPException(status_code=400, detail="From residence ID is required")
        if data.to_residence_id <= 0:
            raise HTTPException(status_code=400, detail="To residence ID is required")
        journey = create_journey_impl(db, data)
        request.logger.info(f"Created journey: {journey}")
        return journey

    @put("/{journey_id:int}")
    async def update_journey(
        self,
        journey_id: int,
        data: JourneyUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> JourneyResponse:
        """Update a journey"""
        db = next(router_dependency)
        journey = update_journey_impl(db, journey_id, data)
        if journey is None:
            raise HTTPException(status_code=404, detail="Journey not found")
        request.logger.info(f"Updated journey: {journey}")
        return journey

    @delete("/{journey_id:int}", status_code=200)
    async def delete_journey(
        self,
        journey_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """Delete a journey"""
        db = next(router_dependency)
        result = delete_journey_impl(db, journey_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Journey not found")
        request.logger.info(f"Deleted journey: {journey_id}")
        return {"id": journey_id, "status": "success", "message": "Journey deleted"}

    @post("/{journey_id:int}/start")
    async def start_journey(
        self,
        journey_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> JourneyResponse:
        """Start a journey"""
        db = next(router_dependency)
        try:
            journey = start_journey_impl(db, journey_id)
            request.logger.info(f"Started journey: {journey_id}")
            return journey
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @post("/{journey_id:int}/complete")
    async def complete_journey(
        self,
        journey_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> JourneyResponse:
        """Complete a journey"""
        db = next(router_dependency)
        try:
            journey = complete_journey_impl(db, journey_id)
            request.logger.info(f"Completed journey: {journey_id}")
            return journey
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @post("/{journey_id:int}/cancel")
    async def cancel_journey(
        self,
        journey_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> JourneyResponse:
        """Cancel a journey"""
        db = next(router_dependency)
        try:
            journey = cancel_journey_impl(db, journey_id)
            request.logger.info(f"Cancelled journey: {journey_id}")
            return journey
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @post("/{journey_id:int}/items")
    async def add_journey_item(
        self,
        journey_id: int,
        data: JourneyItemCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> JourneyResponse:
        """Add an item to a journey"""
        db = next(router_dependency)
        try:
            journey = add_journey_item_impl(db, journey_id, data)
            request.logger.info(f"Added item to journey {journey_id}")
            return journey
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @delete("/{journey_id:int}/items/{item_id:int}", status_code=200)
    async def remove_journey_item(
        self,
        journey_id: int,
        item_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> JourneyResponse:
        """Remove an item from a journey"""
        db = next(router_dependency)
        try:
            journey = remove_journey_item_impl(db, journey_id, item_id)
            request.logger.info(f"Removed item {item_id} from journey {journey_id}")
            return journey
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @post("/{journey_id:int}/pack/{item_id:int}")
    async def pack_journey_item(
        self,
        journey_id: int,
        item_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> JourneyResponse:
        """Mark a journey item as packed"""
        db = next(router_dependency)
        try:
            journey = pack_journey_item_impl(db, journey_id, item_id)
            request.logger.info(f"Packed item {item_id} in journey {journey_id}")
            return journey
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @post("/{journey_id:int}/unpack/{item_id:int}")
    async def unpack_journey_item(
        self,
        journey_id: int,
        item_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> JourneyResponse:
        """Mark a journey item as unpacked"""
        db = next(router_dependency)
        try:
            journey = unpack_journey_item_impl(db, journey_id, item_id)
            request.logger.info(f"Unpacked item {item_id} in journey {journey_id}")
            return journey
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
