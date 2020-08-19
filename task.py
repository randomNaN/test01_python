# -*- coding: utf-8 -*-
from mongoengine import *
import enum
import random
import unittest


class ImagesEnum(enum.Enum):
    cover = 'cover'
    background = 'background'
    foreground = 'foreground'


class QualityEnum(enum.IntEnum):
    LD = 0
    SD = 1
    HD = 2
    FULL_HD = 3


class File(EmbeddedDocument):
    path = StringField()
    quality = IntField()


class Quote(EmbeddedDocument):
    source = StringField()
    text = StringField()


class Episode(EmbeddedDocument):
    num = IntField()
    alias = StringField()
    files = EmbeddedDocumentListField('File')


class Season(Document):
    num = IntField()
    alias = StringField()
    episodes = EmbeddedDocumentListField('Episode', db_field='items')
    meta = {
        'collection': 'products',
        'allow_inheritance': True
    }


class Series(Document):
    title = StringField()
    alias = StringField()
    description = StringField()
    seasons = ListField(ReferenceField('Season'), db_field='items')
    quote = EmbeddedDocumentField('Quote')
    images = MapField(URLField())
    meta = {
        'collection': 'products',
        'allow_inheritance': True
    }


class TestTask(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        connect('test', host='mongo')

    def test_01_create_documents(self):
        def __quote(i):
            source = 'QuoteSource %i' % i
            return {'source': source, 'text': 'test quote'}

        def __images(i):
            return {img.value: 'image path %i' % i for img in ImagesEnum}

        def __files():
            files = list()
            for i in QualityEnum:
                f = File(quality=i, path='file path %i' % i)
                files.append(f)
            return files

        def __episodes():
            episodes = list()
            for i in range(0, random.randint(1, 30)):
                s = Episode(num=i, alias='episode%i' % i, files=__files())
                episodes.append(s)
            return episodes

        def __seasons():
            seasons = list()
            for i in range(0, random.randint(1, 10)):
                s = Season(num=i, alias='season%i' % i, episodes=__episodes())
                s.save()
                seasons.append(s)
            return seasons

        def __series():
            series = list()
            for i in range(0, random.randint(1, 10)):
                s = Series.objects(
                    title='series %i' % i,
                    alias='series%i' % i
                    ).modify(
                        upsert=True,
                        new=True,
                        set__quote=__quote(i),
                        set__images=__images(i),
                        set__description='description %i' % i,
                        set__seasons=__seasons())
                series.append(s)
            return series
        self.assertTrue(__series())

    def test_02_create_documents(self):
        """
            Напишите запрос который вернет ответ следующего формата:
            [
              {
                "path": "/series/<alias сериала>",
                "title": "<title сериала>",
                "description": "<description сериала>",
                "cover": "<изображение из поля images с ключем ImagesEnum.cover>",
                "quote": "<значение quote.text>",
                "quote_source": "<значение quote.source>",
                "slide": {
                  "background": "<изображение из поля images с ключем ImagesEnum.background>",
                  "foreground": "<изображение из поля images с ключем ImagesEnum.foreground>"
                }
                "seasons": [
                  {
                    "path": "/series/<alias сериала>/<alias сезона>",
                    "title": "<num сезона> сезон",
                    "episodes": [
                      {
                        "path": "/series/<alias сериала>/<alias сезона>/<alias эпизода>",
                        "title": "Эпизод <num сезона>",
                        "files": [
                          {
                            "path": "<path файла>",
                            "label": "<название enum поля QualityEnum>",
                            "quality": "<значения enum поля QualityEnum>"
                          }
                        ]
                      }
                    ]
                  }
                ]
              }
            ]
        """
        pipeline = [
            { "$lookup" : {
                "from" : "products",
                "let" : { "seasons" : "$items", "series_name" : "$alias" },
                "pipeline" : [
                    { "$match" : {
                        "$expr" : { 
                            "$and" : [
                                { "_cls": "Season" },
                                { "$in": [ "$_id", "$$seasons" ] }
                                ] 
                            }   
                        } 
                    },
                    { "$project" : {
                            "path" : { "$concat" : ["/series/", "$$series_name", "/", "$alias"] },
                            "title" : { "$concat" : [ { "$toString": { "$add" : ["$num", 1] } }, " сезон"] },
                            "episodes" : {
                                "$map" : {
                                    "input" : "$items",
                                    "as" : "episode",
                                    "in" : {
                                        "path" : { "$concat" : ["/series/", "$$series_name", "/", "$alias", "/", "$$episode.alias"] },
                                        "title" : { "$concat" : ["Эпизод ", { "$toString" : { "$add" : ["$$episode.num", 1]}}] },
                                        "files" : { "$map" : {
                                                "input" : "$$episode.files",
                                                "as" : "file",
                                                "in" : {
                                                    "path" : "$$file.path",
                                                    "label" : { "$arrayElemAt" : [ [quality.name for quality in QualityEnum] , "$$file.quality"]},
                                                    "quality" : "$$file.quality"
                                                } 
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                ],
                "as" : "seasons"
                }
            },
            { "$project" : {
                    "_id": 0, "path": { "$concat": ["/series/", "$alias"]}, "title": 1,
                    "description": 1, "cover": "$images.cover", "quote": "$quote.text",
                    "quote_source": "$quote.source",
                    "slide": { "background": "$images.background", "foreground": "$images.foreground" },
                    "seasons": { "path" : 1, "title" : 1, "episodes" : 1}
                }
            }
        ]
        print(pipeline)
        data = list(Series.objects().aggregate(pipeline))
        print(data[0])
        #pass

if __name__ == '__main__':
    unittest.main()
