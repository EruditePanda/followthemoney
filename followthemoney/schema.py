from banal import ensure_list

from followthemoney.property import Property
from followthemoney.exc import InvalidData, InvalidModel
from followthemoney.util import gettext


class Schema(object):
    """Defines the abstract data model.

    Schema items define the entities and links available in the model.
    """

    def __init__(self, model, name, data):
        self._model = model
        self.name = name
        self.data = data
        self.icon = data.get('icon')
        self._label = data.get('label', name)
        self._plural = data.get('plural', self.label)
        self._description = data.get('description')
        self._extends = ensure_list(data.get('extends'))
        self.featured = ensure_list(data.get('featured'))

        # Do not show in listings:
        self.abstract = data.get('abstract', False)

        # Try to perform fuzzy matching. Fuzzy similarity search does not
        # make sense for entities which have a lot of similar names, such
        # as land plots, assets etc.
        self.matchable = data.get('matchable', True)

        self._own_properties = []
        for name, prop in data.get('properties', {}).items():
            self._own_properties.append(Property(self, name, prop))

    @property
    def label(self):
        return gettext(self._label)

    @property
    def plural(self):
        return gettext(self._plural)

    @property
    def description(self):
        return gettext(self._description)

    @property
    def extends(self):
        """Return the inherited schemata."""
        for base in self._extends:
            basecls = self._model.get(base)
            if basecls is None:
                raise InvalidModel("No such schema: %s" % base)
            yield basecls

    @property
    def schemata(self):
        """Return the full inheritance chain."""
        seen = set([self])
        yield self
        for base in self.extends:
            for schema in base.schemata:
                if schema not in seen:
                    seen.add(schema)
                    yield schema

    @property
    def descendants(self):
        for schema in self._model:
            if schema == self:
                continue
            if self in schema.schemata:
                yield schema

    @property
    def matchable_schemata(self):
        """The set of comparable types."""
        if not self.matchable:
            return
        # This is used by the cross-referencer to determine what
        # other schemata should be considered for matches. For
        # example, a Company may be compared to a Legal Entity,
        # but it makes no sense to compare it to an Aircraft.
        matchable = set(self.schemata)
        for schema in self.descendants:
            matchable.add(schema)
        for schema in matchable:
            if schema.matchable:
                yield schema

    @property
    def names(self):
        return [s.name for s in self.schemata]

    def is_a(self, parent):
        for schema in self.schemata:
            if schema == parent:
                return True
        return False

    def __eq__(self, other):
        other = self._model.get(other)
        return other.name == self.name

    def __hash__(self):
        return hash(self.name)

    @property
    def properties(self):
        """Return properties, those defined locally and in ancestors."""
        if not hasattr(self, '_properties'):
            self._properties = {}
            for schema in self.extends:
                for name, prop in schema.properties.items():
                    self._properties[name] = prop
            for prop in self._own_properties:
                self._properties[prop.name] = prop
        return self._properties

    def get(self, name):
        return self.properties.get(name)

    def validate(self, data):
        """Validate a dataset against the given schema.

        This will also drop keys which are not present as properties.
        """
        result = {}
        errors = {}
        for name, prop in self.properties.items():
            if not prop.required and name not in data:
                continue
            values = data.get(name)
            values, error = prop.validate(values)
            if error is not None:
                errors[name] = error
            if len(values):
                result[name] = values
        if len(errors):
            raise InvalidData(errors)
        return result

    def invert(self, entity, cleaned=True):
        """Invert the properties of an entity into their normalised form."""
        properties = entity.get('properties', {})

        # Generate inverted representations of the data stored in properties.
        for name, prop in self.properties.items():
            values = properties.get(name, [])
            if not len(values):
                continue

            # Add inverted properties. This takes all the properties
            # of a specific type (names, dates, emails etc.)
            if prop.invert:
                if prop.invert not in entity:
                    entity[prop.invert] = []
                for norm in prop.type.normalize(values, cleaned=cleaned):
                    if norm not in entity[prop.invert]:
                        entity[prop.invert].append(norm)

        return entity

    def to_dict(self):
        data = {
            'label': self.label,
            'plural': self.plural,
            'icon': self.icon,
            'abstract': self.abstract,
            'matchable': self.matchable,
            'description': self.description,
            'featured': self.featured,
            'properties': {}
        }
        for name, prop in self.properties.items():
            data['properties'][name] = prop.to_dict()
        return data

    def __repr__(self):
        return '<Schema(%r)>' % self.name
