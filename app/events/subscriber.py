class EventSubscriber:


    def __init__(self):

        self.handlers = {}



    def subscribe(
        self,
        event_type,
        handler
    ):

        self.handlers[event_type] = handler



    def handle(
        self,
        event
    ):


        handler = self.handlers.get(

            event.event_type

        )


        if handler:

            handler(event)
