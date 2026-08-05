class EventBus:


    def __init__(
        self
    ):

        self.events = []

        self.subscribers = []



    def subscribe(
        self,
        subscriber
    ):

        self.subscribers.append(
            subscriber
        )



    def publish(
        self,
        event
    ):


        self.events.append(
            event
        )


        print(
            "\nEVENT:"
        )

        print(
            event.to_dict()
        )


        for subscriber in self.subscribers:

            subscriber.handle(
                event
            )



    def get_events(
        self
    ):

        return [

            event.to_dict()

            for event in self.events

        ]
