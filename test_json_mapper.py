import json_mapper
import pytest
import logging

# test code for the Media_Sifter class using pytest
def test_is_a_metadata_sidecar():
    jm = json_mapper.JSON_Mapper('folder')
    jm.json_document = {}
    assert jm.is_a_metadata_sidecar() == False
    jm.json_document = {
  "title": "IMG_0396.JPG",
  "description": "",
  "imageViews": "333",
}
    assert jm.is_a_metadata_sidecar() == True
    jm.json_document = {
  "description": "",
  "imageViews": "333",
}
    assert jm.is_a_metadata_sidecar() == False
    jm.json_document = {
  "title": "IMG_0396.JPG",
  "imageViews": "333",
}
    assert jm.is_a_metadata_sidecar() == False
    jm.json_document = {
  "title": "IMG_0396.JPG",
  "description": "",
}
    assert jm.is_a_metadata_sidecar() == False

@pytest.fixture
def cwd(fs, monkeypatch):
    fs.cwd = "/my/path"
    monkeypatch.setenv("HOME", "/home/user")

def test_create_mapper(fs, cwd, caplog):
    # test skipping json files with wrong contents
    wrong_json1 = """
{}
"""
    wrong_json2 = """
{
  "description": "",
  "imageViews": "333"
}
"""
    wrong_json3 = """
{
  "title": "IMG_0396.JPG",
  "description": ""
}
"""
    fs.create_file("/my/path/metadata.json", contents=wrong_json1)
    fs.create_file("/my/path/metadata2.json", contents=wrong_json2)
    fs.create_file("/my/path/metadata3.json", contents=wrong_json3)
    # test a valid json file but missing media file
    right_json1 = """
{
  "title": "image.jpg",
  "description": "",
  "imageViews": "333"
}
"""
    fs.create_file("/my/path/image.jpg.json", contents=right_json1)
    jm = json_mapper.JSON_Mapper('/my/path')
    mpr = jm.create_mapper()
    assert mpr == {}

    # now test a valid json file with a media file
    fs.create_file("/my/path/image.jpg")
    mpr = jm.create_mapper()
    assert mpr == {'image.jpg': 'image.jpg.json'}

    # test media file with name > 46 chars
    long_file_json1 = """
{
  "title": "123456789012345678901234567890123456789012345678901.jpg",
  "description": "",
  "imageViews": "333"
}
"""
    fs.create_file("/my/path/1234567890123456789012345678901234567890123456.json", contents=long_file_json1)
    fs.create_file("/my/path/1234567890123456789012345678901234567890123456.jpg")
    mpr = jm.create_mapper()
    assert mpr == {
        'image.jpg': 'image.jpg.json',
        '1234567890123456789012345678901234567890123456.jpg':
          '1234567890123456789012345678901234567890123456.json'
          }

    # test media file with name > 46 chars split in extension
    long_file_json2 = """
{
  "title": "1234567890123456789012345678901234567890123.jpg",
  "description": "",
  "imageViews": "333"
}
"""
    fs.create_file("/my/path/1234567890123456789012345678901234567890123.jp.json", contents=long_file_json2)
    fs.create_file("/my/path/1234567890123456789012345678901234567890123.jpg")
    mpr = jm.create_mapper()
    assert mpr == {
        'image.jpg': 'image.jpg.json',
        '1234567890123456789012345678901234567890123456.jpg':
          '1234567890123456789012345678901234567890123456.json',
        '1234567890123456789012345678901234567890123.jpg':
          '1234567890123456789012345678901234567890123.jp.json'
          }

def test_create_mapper_47_char_file_case(fs, cwd, caplog):
    # test media file with name > 46 chars where target media file has 47 chars randomly
    long_file_json = """
{
  "title": "original_fa7485b9-9574-4dd2-a7bd-74cbb1542c2e_20220522_182714.jpg",
  "description": "",
  "imageViews": "333"
}
"""
    fs.create_file("/my/path/original_fa7485b9-9574-4dd2-a7bd-74cbb1542c2e_.json", contents=long_file_json)
    fs.create_file("/my/path/original_fa7485b9-9574-4dd2-a7bd-74cbb1542c2e_2.jpg")
    jm = json_mapper.JSON_Mapper('/my/path')
    mpr = jm.create_mapper()
    assert mpr == {
        'original_fa7485b9-9574-4dd2-a7bd-74cbb1542c2e_2.jpg':
          'original_fa7485b9-9574-4dd2-a7bd-74cbb1542c2e_.json'
          }

def test_create_mapper_numbered_cases(fs, cwd, caplog):
    # test the various cases where media and json files have the same basic name so numbered extensions are used
    file_json1 = """
{
  "title": "image.jpg",
  "description": "",
  "imageViews": "333"
}
"""
    fs.create_file("/my/path/image.jpg.json", contents=file_json1)
    fs.create_file("/my/path/image.jpg")
    fs.create_file("/my/path/image.jpg(1).json", contents=file_json1)
    fs.create_file("/my/path/image(1).jpg")
    fs.create_file("/my/path/image.jpg(2).json", contents=file_json1)
    fs.create_file("/my/path/image(2).jpg")
    # the next json file only exists as a json - no media file - we will skip it
    fs.create_file("/my/path/image.jpg(3).json", contents=file_json1)
    # this media file doesn't have a matching json - we will also skip it
    fs.create_file("/my/path/image(4).jpg")
    fs.create_file("/my/path/image.jpg(5).json", contents=file_json1)
    fs.create_file("/my/path/image(5).jpg")
    # now test a special case where a file clashes with the numbering scheme!
    file_json2 = """
{
  "title": "image(6).jpg",
  "description": "",
  "imageViews": "333"
}
"""
    fs.create_file("/my/path/image(6).jpg.json", contents=file_json2)
    fs.create_file("/my/path/image(6).jpg")
    # for subsequent files our index numbers are off by one!
    fs.create_file("/my/path/image.jpg(6).json", contents=file_json1)
    fs.create_file("/my/path/image(7).jpg")

    jm = json_mapper.JSON_Mapper('/my/path')
    mpr = jm.create_mapper()
    assert mpr == {
        'image.jpg': 'image.jpg.json',
        'image(1).jpg': 'image.jpg(1).json',
        'image(2).jpg': 'image.jpg(2).json',
        'image(5).jpg': 'image.jpg(5).json',
        'image(6).jpg': 'image(6).jpg.json',
        'image(7).jpg': 'image.jpg(6).json',
          }

def test_create_mapper_odd_cases(fs, cwd, caplog):
    # test the case where media file is missing .jpg extension?!
    file_json1 = """
{
  "title": "image",
  "description": "",
  "imageViews": "333"
}
"""
    fs.create_file("/my/path/image.json", contents=file_json1)
    fs.create_file("/my/path/image.jpg")

    jm = json_mapper.JSON_Mapper('/my/path')
    mpr = jm.create_mapper()
    assert mpr == {
        'image.jpg': 'image.json',
    }

def test_create_mapper_exception1(fs, cwd, caplog):
    # test the case where the initial numbered media file is missing
    file_json1 = """
{
  "title": "image.jpg",
  "description": "",
  "imageViews": "333"
}
"""
    fs.create_file("/my/path/image.jpg(4).json", contents=file_json1)
    fs.create_file("/my/path/image(4).jpg")

    jm = json_mapper.JSON_Mapper('/my/path')
    try:
        mpr = jm.create_mapper()
        assert False
    except Exception:
        assert True

def test_create_mapper_exception2(fs, cwd, caplog):
    # test the case where the denumbered target doesn't match what is in the json file
    file_json1 = """
{
  "title": "imagey.jpg",
  "description": "",
  "imageViews": "333"
}
"""
    fs.create_file("/my/path/image.jpg(1).json", contents=file_json1)
    fs.create_file("/my/path/image(1).jpg")

    jm = json_mapper.JSON_Mapper('/my/path')
    try:
        mpr = jm.create_mapper()
        assert False
    except Exception:
        assert True

def test_create_mapper_exception3(fs, cwd, caplog):
    # test the case where the there is a mismatch with the json contents and the file isn't a numbered one
    file_json1 = """
{
  "title": "imagey.jpg",
  "description": "",
  "imageViews": "333"
}
"""
    fs.create_file("/my/path/image.jpg.json", contents=file_json1)
    fs.create_file("/my/path/image.jpg")

    jm = json_mapper.JSON_Mapper('/my/path')
    try:
        mpr = jm.create_mapper()
        assert False
    except Exception:
        assert True

def test_create_mapper_clash_entry(fs, cwd, caplog):
    # test a valid json file but missing media file
    file_json1 = """
{
  "title": "image.jpg",
  "description": "",
  "imageViews": "333"
}
"""
    fs.create_file("/my/path/image.jpg.json", contents=file_json1)
    fs.create_file("/my/path/image.jpg")
    fs.create_file("/my/path/image.jpg(1).json", contents=file_json1)
    fs.create_file("/my/path/image(1).jpg")
    fs.create_file("/my/path/image.jpg(2).json", contents=file_json1)
    fs.create_file("/my/path/image(2).jpg")
    jm = json_mapper.JSON_Mapper('/my/path')
    # artificially create a clashing entry - shouldn't cause a problem
    jm.mapper = {'image(1).jpg': 'potatoes'}
    mpr = jm.create_mapper()
    assert mpr == {
        'image.jpg': 'image.jpg.json',
        'image(1).jpg': 'potatoes',
        'image(2).jpg': 'image.jpg(2).json'
    }

def test_create_mapper_long_filename_numbered(fs, cwd, caplog):

    # test media file with name > 46 chars and number index with interrupted file extension
    long_file_json1 = """
{
  "title": "580D3E5E-2C01-44EC-AE9F-9D5D16AABBE1-EFFECTS.jpg",
  "description": "",
  "imageViews": "333"
}
"""
    fs.create_file("/my/path/580D3E5E-2C01-44EC-AE9F-9D5D16AABBE1-EFFECTS.j.json", contents=long_file_json1)
    fs.create_file("/my/path/580D3E5E-2C01-44EC-AE9F-9D5D16AABBE1-EFFECTS.jpg")
    fs.create_file("/my/path/580D3E5E-2C01-44EC-AE9F-9D5D16AABBE1-EFFECTS.j(1).json", contents=long_file_json1)
    fs.create_file("/my/path/580D3E5E-2C01-44EC-AE9F-9D5D16AABBE1-EFFECTS(1).jpg")
    jm = json_mapper.JSON_Mapper('/my/path')
    mpr = jm.create_mapper()
    assert mpr == {
        '580D3E5E-2C01-44EC-AE9F-9D5D16AABBE1-EFFECTS.jpg':
          '580D3E5E-2C01-44EC-AE9F-9D5D16AABBE1-EFFECTS.j.json',
        '580D3E5E-2C01-44EC-AE9F-9D5D16AABBE1-EFFECTS(1).jpg':
          '580D3E5E-2C01-44EC-AE9F-9D5D16AABBE1-EFFECTS.j(1).json'
          }
