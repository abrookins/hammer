Hammer
======

A library used to generate JSON Schemas (draft 4) from Colander schemas.

Note: This library is under active development and not yet ready for use.


Working
=======

SchemaTypes:

    - colander.Int
    - colander.Integer
    - colander.Float
    - colander.String
    - colander.Str
    - colander.Bool
    - colander.Dated
    - colander.DateTime
    - colander.Time
    - colander.Money
    - colander.Decimal

Schemas:

    - colander.Schema
    - colander.MappingSchema
    - colander.Mapping
    - colander.Sequence
    - colander.Tuple

Validators:

    - colander.Regex (also handles colander.url)
    - colander.Email
    - colander.Range
    - colander.Length
    - colander.OneOf


Needs Attention
===============

Validators:

    - colander.All
    - colander.ContainsOnly
    - colander.luhnok

SchemaTypes that become "floats" (is this correct?):

    - colander.Money
    - colander.Decimal


