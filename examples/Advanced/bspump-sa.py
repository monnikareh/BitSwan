import bspump
from bspump.trigger import OpportunisticTrigger
from bspump.common import PPrintSink, NullSink
from bspump import BSPumpApplication, Pipeline, Processor
from bspump.analyzer import SessionAnalyzer, TimeWindowAnalyzer
import bspump.random

import logging
import time

import bspump.asab as asab


##
L = logging.getLogger(__name__)
##


class MyApplication(BSPumpApplication):
    def __init__(self):
        super().__init__()

        svc = self.get_service("bspump.PumpService")

        svc.add_pipeline(MyPipeline(self))


class MyPipeline(Pipeline):
    def __init__(self, app, pipeline_id=None):
        super().__init__(app, pipeline_id)

        self.build(
            bspump.random.RandomSource(
                app,
                self,
                config={
                    "number": 300,
                    "upper_bound": 10,
                    "field": "user",
                    "prefix": "",
                },
            ).on(bspump.trigger.OpportunisticTrigger(app, chilldown_period=0.1)),
            bspump.random.RandomEnricher(
                app,
                self,
                config={"field": "duration", "lower_bound": 1, "upper_bound": 5},
                id="RE0",
            ),
            bspump.random.RandomEnricher(
                app, self, config={"field": "user_link", "upper_bound": 10}, id="RE1"
            ),
            GraphSessionAnalyzer(app, self, config={"analyze_period": 5}),
            NullSink(app, self),
        )


class GraphSessionAnalyzer(SessionAnalyzer):
    def __init__(self, app, pipeline, id=None, config=None):
        super().__init__(
            app,
            pipeline,
            dtype=[("user_link", "U40"), ("duration", "i8")],
            analyze_on_clock=True,
            id=id,
            config=config,
        )

    def predicate(self, context, event):
        if "user" not in event:
            return False

        if "duration" not in event:
            return False

        if "user_link" not in event:
            return False

        return True

    def evaluate(self, context, event):
        # print("kek", event)
        start_time = time.time()
        user_from = event["user"]
        user_to = event["user_link"]
        duration = event["duration"]
        row = self.Sessions.get_row_index(user_from)
        if row is None:
            row = self.Sessions.add_row(user_from)

        self.Sessions.Array[row]["duration"] = duration
        self.Sessions.Array[row]["user_link"] = user_to

        row_ = self.Sessions.get_row_index(user_to)
        if row_ is None:
            self.Sessions.add_row(user_to)

    def analyze(self):
        print("Analyzing!")
        graph = {}
        # self.Sessions.close_row(self.Sessions.get_row_index('user_1'))
        sessions_snapshot = self.Sessions.Array
        for i in range(0, sessions_snapshot.shape[0]):
            if i in self.Sessions.ClosedRows:
                print("indeed")
                continue

            user_from = self.Sessions.get_row_index(i)
            print(user_from)
            user_to = sessions_snapshot[i]["user_link"]
            if user_to == "":
                continue

            link_weight = sessions_snapshot[i]["duration"]
            edge = tuple([user_to, link_weight])
            rev_edge = tuple([user_from, link_weight])

            if user_from not in graph:
                graph[user_from] = [edge]
            else:
                graph[user_from].append(edge)

            if user_to not in graph:
                graph[user_to] = [rev_edge]
            else:
                graph[user_to].append(rev_edge)
            # user_from_idx = self.Sessions.get_row_index(user_from)
            # self.Sessions.close_row(i)

        self.Sessions.flush()
        L.warning("Graph is {}".format(graph))


if __name__ == "__main__":
    app = MyApplication()
    app.run()
