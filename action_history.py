class ActionHistory:
    def __init__(self):
        self.history = []

    def record_action(self, action_type, details):
        """
        Records an action in the history.
        :param action_type: A string representing the type of action (e.g., 'write_file', 'delete_file').
        :param details: A dictionary containing details necessary to undo the action.
        """
        self.history.append({'type': action_type, 'details': details})

    def get_last_action(self):
        """
        Retrieves the last action from the history without removing it.
        :return: The last action dictionary, or None if history is empty.
        """
        if self.history:
            return self.history[-1]
        return None

    def pop_last_action(self):
        """
        Retrieves and removes the last action from the history.
        :return: The last action dictionary, or None if history is empty.
        """
        if self.history:
            return self.history.pop()
        return None
