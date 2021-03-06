# -*- coding: utf-8 -*-

from __future__ import absolute_import

import six

from sentry.api.serializers import serialize, SimpleEventSerializer
from sentry.api.serializers.models.event import SharedEventSerializer, SnubaEvent
from sentry.models import EventError
from sentry.testutils import TestCase
from sentry.utils.samples import load_data
from sentry.testutils.helpers.datetime import iso_format, before_now


class EventSerializerTest(TestCase):
    def test_simple(self):
        event_id = "a" * 32
        event = self.store_event(
            data={"event_id": event_id, "timestamp": iso_format(before_now(minutes=1))},
            project_id=self.project.id,
        )
        result = serialize(event)
        assert result["id"] == event_id
        assert result["eventID"] == event_id

    def test_eventerror(self):
        event = self.store_event(
            data={
                "event_id": "a" * 32,
                "timestamp": iso_format(before_now(minutes=1)),
                "stacktrace": [u"ü"],
            },
            project_id=self.project.id,
            assert_no_errors=False,
        )

        result = serialize(event)
        assert len(result["errors"]) == 1
        assert "data" in result["errors"][0]
        assert result["errors"][0]["type"] == EventError.INVALID_DATA
        assert result["errors"][0]["data"] == {
            u"name": u"stacktrace",
            u"reason": u"expected rawstacktrace",
            u"value": [u"\xfc"],
        }
        assert "startTimestamp" not in result
        assert "timestamp" not in result

    def test_hidden_eventerror(self):
        event = self.store_event(
            data={
                "event_id": "a" * 32,
                "timestamp": iso_format(before_now(minutes=1)),
                "breadcrumbs": [u"ü"],
            },
            project_id=self.project.id,
            assert_no_errors=False,
        )

        result = serialize(event)
        assert result["errors"] == []

    def test_renamed_attributes(self):
        # Only includes meta for simple top-level attributes
        event = self.store_event(
            data={
                "event_id": "a" * 32,
                "timestamp": iso_format(before_now(minutes=1)),
                "extra": {"extra": True},
                "modules": {"modules": "foobar"},
                "_meta": {
                    "extra": {"": {"err": ["extra error"]}},
                    "modules": {"": {"err": ["modules error"]}},
                },
            },
            project_id=self.project.id,
            assert_no_errors=False,
        )

        result = serialize(event)
        assert result["context"] == {"extra": True}
        assert result["_meta"]["context"] == {"": {"err": ["extra error"]}}
        assert result["packages"] == {"modules": "foobar"}
        assert result["_meta"]["packages"] == {"": {"err": ["modules error"]}}

    def test_message_interface(self):
        event = self.store_event(
            data={
                "event_id": "a" * 32,
                "timestamp": iso_format(before_now(minutes=1)),
                "logentry": {"formatted": "bar"},
                "_meta": {"logentry": {"formatted": {"": {"err": ["some error"]}}}},
            },
            project_id=self.project.id,
            assert_no_errors=False,
        )

        result = serialize(event)
        assert result["message"] == "bar"
        assert result["_meta"]["message"] == {"": {"err": ["some error"]}}

    def test_message_formatted(self):
        event = self.store_event(
            data={
                "event_id": "a" * 32,
                "timestamp": iso_format(before_now(minutes=1)),
                "logentry": {"formatted": "baz"},
                "_meta": {"logentry": {"formatted": {"": {"err": ["some error"]}}}},
            },
            project_id=self.project.id,
            assert_no_errors=False,
        )

        result = serialize(event)
        assert result["message"] == "baz"
        assert result["_meta"]["message"] == {"": {"err": ["some error"]}}

    def test_message_legacy(self):
        event = self.store_event(
            data={
                "event_id": "a" * 32,
                "timestamp": iso_format(before_now(minutes=1)),
                "logentry": {"formatted": None},
            },
            project_id=self.project.id,
            assert_no_errors=False,
        )

        event.message = "search message"

        result = serialize(event)
        assert result["message"] == "search message"

    def test_tags_tuples(self):
        event = self.store_event(
            data={
                "event_id": "a" * 32,
                "timestamp": iso_format(before_now(minutes=1)),
                "tags": [["foo", "foo"], ["bar", "bar"]],
                "_meta": {
                    "tags": {
                        "0": {"1": {"": {"err": ["foo error"]}}},
                        "1": {"1": {"": {"err": ["bar error"]}}},
                    }
                },
            },
            project_id=self.project.id,
            assert_no_errors=False,
        )

        result = serialize(event)
        assert result["tags"][0]["value"] == "bar"
        assert result["tags"][1]["value"] == "foo"
        assert result["_meta"]["tags"]["0"]["value"] == {"": {"err": ["bar error"]}}
        assert result["_meta"]["tags"]["1"]["value"] == {"": {"err": ["foo error"]}}

    def test_tags_dict(self):
        event = self.store_event(
            data={
                "event_id": "a" * 32,
                "timestamp": iso_format(before_now(minutes=1)),
                "tags": {"foo": "foo", "bar": "bar"},
                "_meta": {
                    "tags": {
                        "foo": {"": {"err": ["foo error"]}},
                        "bar": {"": {"err": ["bar error"]}},
                    }
                },
            },
            project_id=self.project.id,
            assert_no_errors=False,
        )

        result = serialize(event)
        assert result["tags"][0]["value"] == "bar"
        assert result["tags"][1]["value"] == "foo"
        assert result["_meta"]["tags"]["0"]["value"] == {"": {"err": ["bar error"]}}
        assert result["_meta"]["tags"]["1"]["value"] == {"": {"err": ["foo error"]}}

    def test_none_interfaces(self):
        event = self.store_event(
            data={
                "event_id": "a" * 32,
                "timestamp": iso_format(before_now(minutes=1)),
                "breadcrumbs": None,
                "exception": None,
                "logentry": None,
                "request": None,
                "user": None,
                "contexts": None,
                "sdk": None,
                "_meta": None,
            },
            project_id=self.project.id,
        )

        result = serialize(event)
        assert not any(e["type"] == "breadcrumbs" for e in result["entries"])
        assert not any(e["type"] == "exception" for e in result["entries"])
        assert not any(e["type"] == "message" for e in result["entries"])
        assert not any(e["type"] == "request" for e in result["entries"])
        assert result["user"] is None
        assert result["sdk"] is None
        assert result["contexts"] == {}
        assert "startTimestamp" not in result

    def test_transaction_event(self):
        event_data = load_data("transaction")
        event = self.store_event(data=event_data, project_id=self.project.id)
        result = serialize(event)
        assert isinstance(result["endTimestamp"], float)
        assert result["endTimestamp"] == event.data.get("timestamp")
        assert isinstance(result["startTimestamp"], float)
        assert result["startTimestamp"] == event.data.get("start_timestamp")
        assert "dateCreated" not in result
        assert "crashFile" not in result
        assert "fingerprints" not in result

    def test_transaction_event_empty_spans(self):
        event_data = load_data("transaction")
        event_data["spans"] = []
        event = self.store_event(data=event_data, project_id=self.project.id)
        result = serialize(event)
        assert result["entries"][0]["type"] == "spans"


class SharedEventSerializerTest(TestCase):
    def test_simple(self):
        event = self.store_event(
            data={"event_id": "a" * 32, "timestamp": iso_format(before_now(minutes=1))},
            project_id=self.project.id,
        )

        result = serialize(event, None, SharedEventSerializer())
        assert result["id"] == "a" * 32
        assert result["eventID"] == "a" * 32
        assert result.get("context") is None
        assert result.get("contexts") is None
        assert result.get("user") is None
        assert result.get("tags") is None
        assert "sdk" not in result
        assert "errors" not in result
        for entry in result["entries"]:
            assert entry["type"] != "breadcrumbs"


class SimpleEventSerializerTest(TestCase):
    def test_user(self):
        """
        Use the SimpleEventSerializer to serialize an event
        """

        group = self.create_group()
        event = SnubaEvent(
            {
                "event_id": "a",
                "project_id": 1,
                "message": "hello there",
                "title": "hi",
                "type": "default",
                "location": "somewhere",
                "culprit": "foo",
                "timestamp": "2011-01-01T00:00:00Z",
                "user_id": "123",
                "email": "test@test.com",
                "username": "test",
                "ip_address": "192.168.0.1",
                "platform": "asdf",
                "group_id": group.id,
                "tags.key": ["sentry:user"],
                "tags.value": ["email:test@test.com"],
            }
        )
        result = serialize(event, None, SimpleEventSerializer())

        # Make sure we didn't have to call out to Nodestore to get the data
        # required to serialize this event and the NodeData is still empty.
        assert (
            event.data._node_data is None
        ), "SimpleEventSerializer should not load Nodestore data."

        assert result["eventID"] == event.event_id
        assert result["projectID"] == six.text_type(event.project_id)
        assert result["groupID"] == six.text_type(group.id)
        assert result["message"] == event.message
        assert result["title"] == event.title
        assert result["location"] == event.location
        assert result["culprit"] == event.culprit
        assert result["dateCreated"] == event.datetime
        assert result["user"]["id"] == event.user_id
        assert result["user"]["email"] == event.email
        assert result["user"]["username"] == event.username
        assert result["user"]["ip_address"] == event.ip_address
        assert result["tags"] == [
            {"key": "user", "value": "email:test@test.com", "query": 'user.email:"test@test.com"'}
        ]

    def test_no_group(self):
        """
        Use the SimpleEventSerializer to serialize an event without group
        """

        event = SnubaEvent(
            {
                "event_id": "a",
                "project_id": 1,
                "message": "hello there",
                "title": "hi",
                "type": "default",
                "location": "somewhere",
                "culprit": "foo",
                "timestamp": "2011-01-01T00:00:00Z",
                "user_id": "123",
                "email": "test@test.com",
                "username": "test",
                "ip_address": "192.168.0.1",
                "platform": "asdf",
                "group_id": None,
                "tags.key": ["sentry:user"],
                "tags.value": ["email:test@test.com"],
            }
        )
        result = serialize(event, None, SimpleEventSerializer())
        assert result["groupID"] is None
