import asyncio

from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.db import get_db
from app.main import app
from app.models import (
    AcceptanceCriterion,
    Epic,
    FeatureDependency,
    Feature,
    Initiative,
    KnowledgeItem,
    KnowledgeRelation,
    Product,
    Project,
    Sprint,
    Task,
    TaskDependency,
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


def test_task_shares_issue_counter_with_feature_and_has_acceptance_criteria(db_session):
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
            await session.flush()

            project = Project(product_id=product.id, name="Web App")
            session.add(project)
            await session.flush()

            task = Task(
                feature_id=feature.id,
                project_id=project.id,
                title="Wire up login form",
                task_type="feature",
                issue_number=2,
            )
            session.add(task)
            await session.flush()

            criterion = AcceptanceCriterion(
                task_id=task.id, format="basic", description="Form submits"
            )
            session.add(criterion)
            await session.commit()

            result = await session.execute(
                select(Task)
                .where(Task.id == task.id)
                .options(
                    selectinload(Task.feature)
                    .selectinload(Feature.epic)
                    .selectinload(Epic.initiative)
                    .selectinload(Initiative.product)
                )
            )
            loaded = result.scalar_one()
            assert loaded.issue_key == "HAND-2"

            result = await session.execute(
                select(AcceptanceCriterion).where(AcceptanceCriterion.task_id == task.id)
            )
            assert result.scalar_one().description == "Form submits"
            break

    asyncio.run(_run())


def test_can_create_task_and_feature_dependencies(db_session):
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

            feature_a = Feature(epic_id=epic.id, name="Login", issue_number=1)
            feature_b = Feature(epic_id=epic.id, name="Logout", issue_number=2)
            session.add_all([feature_a, feature_b])
            await session.flush()

            project = Project(product_id=product.id, name="Web App")
            session.add(project)
            await session.flush()

            task_a = Task(
                feature_id=feature_a.id,
                project_id=project.id,
                title="A",
                task_type="feature",
                issue_number=3,
            )
            task_b = Task(
                feature_id=feature_a.id,
                project_id=project.id,
                title="B",
                task_type="feature",
                issue_number=4,
            )
            session.add_all([task_a, task_b])
            await session.flush()

            task_dep = TaskDependency(task_id=task_a.id, depends_on_task_id=task_b.id)
            feature_dep = FeatureDependency(
                feature_id=feature_a.id, depends_on_feature_id=feature_b.id
            )
            session.add_all([task_dep, feature_dep])
            await session.commit()

            result = await session.execute(
                select(TaskDependency).where(TaskDependency.task_id == task_a.id)
            )
            loaded_task_dep = result.scalar_one()
            assert loaded_task_dep.depends_on_task_id == task_b.id

            result = await session.execute(
                select(FeatureDependency).where(FeatureDependency.feature_id == feature_a.id)
            )
            loaded_feature_dep = result.scalar_one()
            assert loaded_feature_dep.depends_on_feature_id == feature_b.id

            await session.delete(task_b)
            await session.commit()

            result = await session.execute(
                select(TaskDependency).where(TaskDependency.task_id == task_a.id)
            )
            assert result.scalar_one_or_none() is None
            break

    asyncio.run(_run())
