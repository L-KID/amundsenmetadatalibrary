import unittest
from atlasclient.exceptions import BadRequest
from mock import patch, MagicMock

from metadata_service import create_app
from metadata_service.entity.popular_table import PopularTable
from metadata_service.entity.table_detail import (Table, User, Tag, Column)
from metadata_service.entity.tag_detail import TagDetail
from metadata_service.exception import NotFoundException


class TestAtlasProxy(unittest.TestCase):
    def setUp(self):
        self.app = create_app(config_module_class='metadata_service.config.LocalConfig')
        self.app_context = self.app.app_context()
        self.app_context.push()

        with patch('metadata_service.proxy.atlas_proxy.Atlas'):
            # Importing here to make app context work before
            # importing `current_app` indirectly using the AtlasProxy
            from metadata_service.proxy.atlas_proxy import AtlasProxy
            self.proxy = AtlasProxy(host='DOES_NOT_MATTER', port=0000)
            self.proxy._driver = MagicMock()

        self.entity_type = 'TEST_ENTITY'
        self.cluster = 'TEST_CLUSTER'
        self.db = 'TEST_DB'
        self.name = 'TEST_TABLE'
        self.table_id = '69cdc0de-1efa-428f-9c6e-5aa650c24138'

        self.classification_entity = {
            'classifications': [
                {'typeName': 'PII_DATA', 'name': 'PII_DATA'},
            ]
        }

        self.column_id = "5717362e-19a2-4bac-be49-0e4c5851300e"
        self.test_column = {
            'guid': '5717362e-19a2-4bac-be49-0e4c5851300e',
            'typeName': 'COLUMN',
            'attributes': {
                'qualifiedName': 'column@name',
                'type': 'Managed',
                'description': 'column description',
                'position': 1
            }

        }

        self.db_entity = {
            'guid': 'ff6f8097-aead-428a-94ca-3fcb92b02255',
            'updateTime': 234,
            'typeName': self.entity_type,
            'attributes': {
                'qualifiedName': self.db,
                'name': 'self.db',
                'description': 'Dummy DB Description',
                'owner': 'dummy@email.com',
            }
        }

        self.entity1 = {
            'guid': '69cdc0de-1efa-428f-9c6e-5aa650c24138',
            'typeName': self.entity_type,
            'updateTime': 123,
            'attributes': {
                'qualifiedName': 'Table1_Qualified',
                'name': 'Table1',
                'description': 'Dummy Description',
                'owner': 'dummy@email.com',
                'columns': [self.test_column],
                'db': self.db_entity
            },
            'relationshipAttributes': {
                'db': self.db_entity,
                'columns': [self.test_column],
            },
        }
        self.entity1.update(self.classification_entity)

        self.entity2 = {
            'guid': 'eeaf8d38-e986-46fb-a062-88a09c1b728d',
            'updateTime': 234,
            'typeName': self.entity_type,
            'attributes': {
                'qualifiedName': 'Table2_Qualified',
                'name': 'Table1',
                'description': 'Dummy Description',
                'owner': 'dummy@email.com',
                'db': self.db_entity
            },
            'relationshipAttributes': {
                'db': self.db_entity,
            },
        }
        self.entity2.update(self.classification_entity)
        self.entities = {
            'entities': [
                self.entity1,
                self.entity2,
            ]
        }

    def _mock_get_table_entity(self, entity=None):
        mocked_table_entity = MagicMock()
        mocked_table_entity.entity = entity or self.entity1

        if mocked_table_entity.entity == self.entity1:
            mocked_table_entity.referredEntities = {
                self.test_column['guid']: self.test_column
            }
        else:
            mocked_table_entity.referredEntities = {}
        self.proxy._get_table_entity = MagicMock(return_value=mocked_table_entity)
        return mocked_table_entity

    def _mock_get_column(self, entity=None):
        mocked_column_entity = MagicMock()
        mocked_column_entity.entity = entity or self.test_column
        self.proxy._get_column = MagicMock(return_value=mocked_column_entity)
        return mocked_column_entity

    def test_get_ids_from_basic_search(self):
        entity1 = MagicMock()
        entity1.guid = self.entity1['guid']

        entity2 = MagicMock()
        entity2.guid = self.entity2['guid']

        basic_search_response = MagicMock()
        basic_search_response.entities = [entity1, entity2]

        self.proxy._driver.search_basic = MagicMock(return_value=[basic_search_response])
        response = self.proxy._get_ids_from_basic_search(params={})
        expected = ['69cdc0de-1efa-428f-9c6e-5aa650c24138', 'eeaf8d38-e986-46fb-a062-88a09c1b728d']
        self.assertListEqual(response, expected)

    def test_get_rel_attributes_dict(self):
        entity1 = MagicMock()
        entity1.attributes = self.entity1['attributes']

        entity2 = MagicMock()
        entity2.attributes = self.entity2['attributes']

        db_entity = MagicMock()
        db_entity.guid = self.db_entity['guid']

        rel_attr_collection = MagicMock()
        rel_attr_collection.entities = [db_entity]

        self.proxy._driver.entity_bulk = MagicMock(return_value=[rel_attr_collection])
        response = self.proxy._get_rel_attributes_dict(entities=[entity1, entity2],
                                                       attribute='db')
        expected = {
            self.db_entity['guid']: db_entity
        }
        self.assertDictEqual(response, expected)

    def test_get_table_entity(self):
        entity_guid_response = MagicMock()

        self.proxy._driver.entity_guid = MagicMock(
            return_value=entity_guid_response)
        ent = self.proxy._get_table_entity(table_id=self.table_id)
        self.assertEqual(ent.__repr__(), entity_guid_response.__repr__())

    def test_get_table(self):
        self._mock_get_table_entity()
        table_info = {'entity': self.entity_type,
                      'cluster': self.cluster,
                      'db': self.db,
                      'name': self.name}
        response = self.proxy.get_table(table_id=self.table_id, table_info=table_info)

        classif_name = self.classification_entity['classifications'][0]['typeName']
        ent_attrs = self.entity1['attributes']

        col_attrs = self.test_column['attributes']
        exp_col = Column(name=col_attrs['qualifiedName'],
                         description='column description',
                         col_type='Managed',
                         sort_order=col_attrs['position'])
        expected = Table(database=self.entity_type,
                         cluster=self.cluster,
                         schema=self.db,
                         name=self.name,
                         tags=[Tag(tag_name=classif_name, tag_type="default")],
                         description=ent_attrs['description'],
                         owners=[User(email=ent_attrs['owner'])],
                         columns=[exp_col],
                         last_updated_timestamp=self.entity1['updateTime'])
        self.assertEqual(str(expected), str(response))

    def test_get_table_not_found(self):
        table_info = {'entity': self.entity_type,
                      'cluster': self.cluster,
                      'db': self.db,
                      'name': self.name}
        with self.assertRaises(NotFoundException):
            self.proxy._driver.entity_guid = MagicMock(side_effect=Exception('Boom!'))
            self.proxy.get_table(table_id=self.table_id, table_info=table_info)

    def test_get_table_missing_info(self):
        with self.assertRaises(BadRequest):
            local_entity = self.entity1
            local_entity.pop('attributes')
            entity_guid_response = MagicMock()
            entity_guid_response.entity = local_entity

            self.proxy._driver.entity_guid = MagicMock(return_value=entity_guid_response)
            self.proxy.get_table(table_id=self.table_id, table_info={})

    def test_get_popular_tables(self):
        entity1 = MagicMock()
        entity1.typeName = self.entity1['typeName']
        entity1.attributes = self.entity1['attributes']

        entity2 = MagicMock()
        entity2.typeName = self.entity2['typeName']
        entity2.attributes = self.entity2['attributes']

        basic_search_collection = MagicMock()
        basic_search_collection.entities = [entity1, entity2]

        self.proxy._driver.search_basic.create = MagicMock(return_value=basic_search_collection)

        db_entity = MagicMock()
        db_entity.attributes = {
            'qualifiedName': self.db,
            'clusterName': self.cluster
        }

        db_dict = {self.entity1['attributes']['db']['guid']: db_entity}

        self.proxy._get_rel_attributes_dict = MagicMock(return_value=db_dict)

        response = self.proxy.get_popular_tables(num_entries=2)
        ent1_attrs = self.entity1['attributes']
        ent2_attrs = self.entity2['attributes']

        expected = [
            PopularTable(database=self.entity_type, cluster=self.cluster, schema=self.db,
                         name=ent1_attrs['qualifiedName'], description=ent1_attrs['description']),
            PopularTable(database=self.entity_type, cluster=self.cluster, schema=self.db,
                         name=ent2_attrs['qualifiedName'], description=ent1_attrs['description']),
        ]

        self.assertEqual(expected.__repr__(), response.__repr__())

    def test_get_popular_tables_without_db(self):
        attrs_ent1 = self.entity1['attributes']
        attrs_ent1.pop('db')
        entity1 = MagicMock()
        entity1.typeName = self.entity1['typeName']
        entity1.attributes = attrs_ent1

        attrs_ent2 = self.entity2['attributes']
        attrs_ent2.pop('db')
        entity2 = MagicMock()
        entity2.typeName = self.entity2['typeName']
        entity2.attributes = attrs_ent2

        basic_search_collection = MagicMock()
        basic_search_collection.entities = [entity1, entity2]

        self.proxy._driver.search_basic.create = MagicMock(return_value=basic_search_collection)
        self.proxy._get_rel_attributes_dict = MagicMock(return_value=dict())

        response = self.proxy.get_popular_tables(num_entries=2)

        ent1_attrs = self.entity1['attributes']
        ent2_attrs = self.entity2['attributes']

        expected = [
            PopularTable(database=self.entity_type, cluster='', schema='',
                         name=ent1_attrs['qualifiedName'], description=ent1_attrs['description']),
            PopularTable(database=self.entity_type, cluster='', schema='',
                         name=ent2_attrs['qualifiedName'], description=ent1_attrs['description']),
        ]

        self.assertEqual(expected.__repr__(), response.__repr__())

    def test_get_popular_tables_search_exception(self):
        with self.assertRaises(BadRequest):
            self.proxy._driver.search_basic.create = MagicMock(side_effect=BadRequest('Boom!'))
            self.proxy.get_popular_tables(num_entries=2)

    def test_get_table_description(self):
        self._mock_get_table_entity()
        response = self.proxy.get_table_description(table_id=self.table_id)
        self.assertEqual(response, self.entity1['attributes']['description'])

    def test_put_table_description(self):
        self._mock_get_table_entity()
        self.proxy.put_table_description(table_id=self.table_id,
                                         description="DOESNT_MATTER")

    def test_get_tags(self):
        name = "DUMMY_CLASSIFICATION"
        mocked_classif = MagicMock()
        mocked_classif.name = name

        mocked_def = MagicMock()
        mocked_def.classificationDefs = [mocked_classif]

        self.proxy._driver.typedefs = [mocked_def]

        response = self.proxy.get_tags()

        expected = [TagDetail(tag_name=name, tag_count=0)]
        self.assertEqual(response.__repr__(), expected.__repr__())

    def test_add_tag(self):
        tag = "TAG"
        self._mock_get_table_entity()

        with patch.object(self.proxy._driver.entity_bulk_classification, 'create') as mock_execute:
            self.proxy.add_tag(table_id=self.table_id, tag=tag)
            mock_execute.assert_called_with(
                data={'classification': {'typeName': tag}, 'entityGuids': [self.entity1['guid']]}
            )

    def test_delete_tag(self):
        tag = "TAG"
        self._mock_get_table_entity()
        mocked_entity = MagicMock()
        self.proxy._driver.entity_guid = MagicMock(return_value=mocked_entity)

        with patch.object(mocked_entity.classifications(tag), 'delete') as mock_execute:
            self.proxy.delete_tag(table_id=self.table_id, tag=tag)
            mock_execute.assert_called_with()

    def test_add_owner(self):
        owner = "OWNER"
        entity = self._mock_get_table_entity()
        with patch.object(entity, 'update') as mock_execute:
            self.proxy.add_owner(table_id=self.table_id, owner=owner)
            mock_execute.assert_called_with()

    def test_get_column(self):
        response = self._mock_get_column()
        self.assertDictEqual(response.entity, self.test_column)

    def test_get_column_wrong_guid(self):
        with self.assertRaises(NotFoundException):
            self.proxy._driver.entity_guid = MagicMock(side_effect=Exception('Boom!'))
            self.proxy._get_column(column_id=self.column_id)

    def test_get_column_description(self):
        self._mock_get_column()
        response = self.proxy.get_column_description(
            column_id=self.column_id)
        self.assertEqual(response, self.test_column['attributes'].get('description'))

    def test_put_column_description(self):
        self._mock_get_column()
        self.proxy.put_column_description(column_id=self.column_id,
                                          description='DOESNT_MATTER')


if __name__ == '__main__':
    unittest.main()
