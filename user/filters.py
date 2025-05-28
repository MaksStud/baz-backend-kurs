import django_filters
from django.db.models import QuerySet, Q


from .models import BazhayUser


class BazhayUserFilter(django_filters.FilterSet):
    """
    A filter for users based on the username, first_name, and last_name fields.

    Supports partial search (icontains) for each of the fields and sorts the results by the number of matches for the
    specified fields. Users with more matches are displayed first.
    """

    username = django_filters.CharFilter(field_name='username', lookup_expr='icontains')
    first_name = django_filters.CharFilter(field_name='first_name', lookup_expr='icontains')
    last_name = django_filters.CharFilter(field_name='last_name', lookup_expr='icontains')

    class Meta:
        model = BazhayUser
        fields = ['username', 'first_name', 'last_name']

    def filter_queryset(self, queryset: QuerySet) -> QuerySet:
        """
        Filters and sorts the dataset based on matches in the fields username, first_name, last_name.
        Only applies the filter if the value is provided.
        Returns: QuerySet: The filtered and sorted data set, where users with more matches are displayed first.
        """
        username = self.data.get('username', False)
        first_name = self.data.get('first_name', False)
        last_name = self.data.get('last_name', False)

        if not username and not first_name and not last_name:
            return queryset

        queryset = queryset.filter(Q(username__icontains=username, username__isnull=False) |
                                   Q(first_name__icontains=first_name, first_name__isnull=False) |
                                   Q(last_name__icontains=last_name, last_name__isnull=False))

        return queryset
