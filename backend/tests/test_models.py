import asyncio

from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.db import get_db
from app.main import app
from app.models import (
    Epic,
    Feature,
    Initiative,
    KnowledgeItem,
    KnowledgeRelation,
    Product,
    Project,
    Sprint,
)


def test_can_create_full_hierarchy_and_compute_issue_key(db_session):
    async def _run():
        override = app.dependency_overrides[get_db]
        async for session in override():
            product = Product(name="Handoff", key_prefix="HAND")
            session.add(product)
            await session.flush()

            initiative = Initiative(product_id=product.id, name="Core")
            session.add(initiative)
            await session.flush()

            epic = Epic(initiative_id=initiative.id, name="Auth")
            session.add(epic)
            await session.flush()

            feature = Feature(epic_id=epic.id, name="Login", issue_number=1)
            session.add(feature)
            await session.commit()

            result = await session.execute(
                select(Feature)
                .where(Feature.id == feature.id)
                .options(
                    selectinload(Feature.epic)
                    .selectinload(Epic.initiative)
                    .selectinload(Initiative.product)
                )
            )
            loaded = result.scalar_one()
            assert loaded.issue_key == "HAND-1"
            break

    asyncio.run(_run())


def test_can_create_project_and_sprint_and_link_feature_default_project(db_session):
    async def _run():
        override = app.dependency_overrides[get_db]
        async for session in override():
            product = Product(name="Handoff", key_prefix="HAND")
            session.add(product)
            await session.flush()

            project = Project(product_id=product.id, name="Web App")
            sprint = Sprint(product_id=product.id, name="Sprint 1")
            session.add_all([project, sprint])
            await session.flush()

            initiative = Initiative(product_id=product.id, name="Core")
            session.add(initiative)
            await session.flush()

            epic = Epic(initiative_id=initiative.id, name="Auth")
            session.add(epic)
            await session.flush()

            feature = Feature(
                epic_id=epic.id, name="Login", issue_number=1, default_project_id=project.id
            )
            session.add(feature)
            await session.commit()

            result = await session.execute(select(Feature).where(Feature.id == feature.id))
            loaded = result.scalar_one()
            assert loaded.default_project_id == project.id
            break

    asyncio.run(_run())


def test_can_create_knowledge_item_and_relation(db_session):
    async def _run():
        override = app.dependency_overrides[get_db]
        async for session in override():
            product = Product(name="Handoff", key_prefix="HAND")
            session.add(product)
            await session.flush()

            item_a = KnowledgeItem(
                type="decision",
                scope="product",
                scope_ref_id=product.id,
                content={
                    "kind": "decision",
                    "subject": "DB",
                    "chosen": "Postgres",
                    "alternatives_considered": ["MySQL"],
                    "rationale": "team familiarity",
                },
            )
            item_b = KnowledgeItem(
                type="decision",
                scope="product",
                scope_ref_id=product.id,
                content={
                    "kind": "decision",
                    "subject": "DB",
                    "chosen": "MySQL",
                    "alternatives_considered": [],
                    "rationale": "changed our minds",
                },
            )
            session.add_all([item_a, item_b])
            await session.flush()

            relation = KnowledgeRelation(
                from_item_id=item_b.id, to_item_id=item_a.id, relation_type="supersedes"
            )
            session.add(relation)
            await session.commit()

            result = await session.execute(
                select(KnowledgeItem).where(KnowledgeItem.id == item_a.id)
            )
            loaded = result.scalar_one()
            assert loaded.content["chosen"] == "Postgres"
            break

    asyncio.run(_run())
