import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import ZhihuContent as DbContent
from media_platform.zhihu.help import ZhihuExtractor


def page(answers, questions=None):
    data = {'initialState': {'entities': {'answers': answers, 'questions': questions or {}}}}
    return '<script id="js-initialData" type="text/json">' + json.dumps(data) + '</script>'


def sample():
    return {'id': '100', 'type': 'answer', 'question': {'id': '10', 'title': 'Question'},
            'content': '<p>Answer</p>', 'createdTime': 1580897763, 'updatedTime': 1581068304,
            'voteupCount': 342, 'commentCount': 135, 'favlistsCount': 22, 'thanksCount': 99,
            'contentNeedTruncated': False,
            'reaction': {'statistics': {'likeCount': 35}}, 'author': {}}


def test_page_camelcase_fields_and_question_entity_are_extracted():
    question = {'id': '10', 'title': 'Question', 'detail': '<p>Details</p><img src="https://example.org/pic.jpg">',
                'answerCount': 366, 'commentCount': 19, 'followerCount': 603,
                'visitCount': 1549787, 'voteupCount': 17}
    html = page({'999': dict(sample(), id='999'), '100': sample()}, {'10': question})
    item = ZhihuExtractor().extract_answer_content_from_html(html, '100', '10')
    assert item.content_id == '100'
    assert item.question_title == item.title == 'Question'
    assert item.question_detail == 'Details'
    assert 'pic.jpg' in item.question_detail_html
    assert item.content_html == '<p>Answer</p>'
    assert item.voteup_count == 342
    assert item.comment_count == 135
    assert item.favlists_count == 22
    assert item.like_count == 35
    assert item.thanks_count == 99  # Never infer likes from thanks, even if one sample agrees.
    assert item.question_comment_count == 19
    assert item.question_answer_count == 366
    assert item.question_follower_count == 603
    assert item.question_visit_count == 1549787
    assert item.question_voteup_count == 17
    assert item.created_time == 1580897763
    assert item.updated_time == 1581068304
    assert item.content_need_truncated is False


def test_api_snakecase_zero_is_not_overwritten_by_reaction_fallback():
    answer = {'id': '100', 'type': 'answer', 'question': {'id': '10', 'title': 'Q'},
              'content': 'body', 'voteup_count': 0, 'comment_count': 0, 'favlists_count': 0,
              'created_time': 1580897763, 'updated_time': 1581068304,
              'reaction': {'statistics': {'upVoteCount': 50, 'commentCount': 51, 'favorites': 52}}}
    item = ZhihuExtractor()._extract_answer_content(answer)
    assert (item.voteup_count, item.comment_count, item.favlists_count) == (0, 0, 0)
    assert item.created_time == 1580897763
    assert item.like_count is None


def test_missing_counters_and_detail_are_null_not_fabricated_zero_or_excerpt():
    answer = {'id': '100', 'type': 'answer', 'question': {'id': '10'}, 'content': 'body',
              'excerpt': 'Answer excerpt, never question detail'}
    item = ZhihuExtractor()._extract_answer_content(answer)
    for field in ['voteup_count', 'comment_count', 'favlists_count', 'like_count',
                  'thanks_count', 'question_detail', 'question_detail_html',
                  'question_title', 'created_time', 'updated_time']:
        assert getattr(item, field) is None
    assert item.desc.startswith('Answer excerpt')


def test_empty_question_detail_is_known_empty_and_distinct_from_missing():
    item = ZhihuExtractor()._extract_answer_content(sample(), {'id': '10', 'detail': ''})
    assert item.question_detail == item.question_detail_html == ''


def test_reaction_fallback_and_truncation_flag_are_preserved():
    answer = {'id': '100', 'type': 'answer', 'question': {'id': '10'}, 'content': 'excerpt',
              'contentNeedTruncated': True,
              'reaction': {'statistics': {'upVoteCount': 4, 'commentCount': 5, 'favorites': 6, 'likeCount': 7}}}
    item = ZhihuExtractor()._extract_answer_content(answer)
    assert (item.voteup_count, item.comment_count, item.favlists_count, item.like_count) == (4, 5, 6, 7)
    assert item.content_need_truncated is True


def test_missing_target_never_substitutes_a_recommended_answer():
    html = page({'999': dict(sample(), id='999')})
    assert ZhihuExtractor().extract_answer_content_from_html(html, '100', '10') is None


def test_wrong_question_is_rejected():
    with pytest.raises(ValueError, match='different question'):
        ZhihuExtractor().extract_answer_content_from_html(page({'100': sample()}), '100', '11')


def test_ambiguous_page_requires_target_id():
    with pytest.raises(ValueError, match='answer_id'):
        ZhihuExtractor().extract_answer_content_from_html(page({'100': sample(), '999': dict(sample(), id='999')}))


def test_new_database_schema_round_trips_extended_fields_and_missing_values():
    engine = create_engine('sqlite://')
    DbContent.__table__.create(engine)
    item = ZhihuExtractor()._extract_answer_content(sample(), {'id': '10', 'detail': '<p>Details</p>'})
    with Session(engine) as session:
        session.add(DbContent(**item.model_dump()))
        session.commit()
        stored = session.query(DbContent).one()
        assert stored.favlists_count == 22
        assert stored.like_count == 35
        assert stored.question_detail == 'Details'
        assert stored.question_comment_count is None
        assert stored.content_need_truncated is False


def test_new_database_schema_preserves_unknown_answer_counts_as_null():
    engine = create_engine('sqlite://')
    DbContent.__table__.create(engine)
    item = ZhihuExtractor()._extract_answer_content({'id': '100', 'type': 'answer', 'content': 'body'})
    with Session(engine) as session:
        session.add(DbContent(**item.model_dump()))
        session.commit()
        stored = session.query(DbContent).one()
        assert stored.voteup_count is None
        assert stored.comment_count is None
