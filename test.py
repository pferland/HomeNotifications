def sort_list(sorting, list=[]):
    if sorting.lower() == "asc" or "desc" or "none":
        if len(list) == 1 or sorting.lower() == "none":
            return list
        elif len(list) > 1:
            if sorting.lower() == "asc":
                return list.sort()
            else:
                return list.sort(reversed=True)
        else:
            return "Please enter a list with length greater than 0."
    else:
        return "Please enter a valid sorting order."


print(sort_list("asc", [2, 1, 3]))
