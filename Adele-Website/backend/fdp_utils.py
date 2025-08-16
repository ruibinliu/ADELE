from typing import List, Union, Dict, Any
import uuid
from pydantic import ConfigDict, Field, ValidationError
from rdflib import DCAT, DCTERMS, SKOS, Namespace, URIRef, RDF, RDFS, Literal
from rdflib.namespace import DefinedNamespace
from sempyro.dcat import DCATDataset
from sempyro.rdf_model import LiteralField
from pydantic import field_validator
from rdflib import RDF, RDFS, Literal

from sempyro.dcat.dcat_distribution import DCATDistribution
from sempyro.utils.validator_functions import force_literal_field

from sempyro.dcat.dcat_distribution import DCATDistribution
from sempyro.foaf.agent import Agent
from sempyro.vcard.vcard import VCard

import fairclient.fdpclient
from datetime import datetime
from rdflib.namespace import XSD
from pymongo import MongoClient 
from settings import *

client = MongoClient(MONGO_URI)
dbMetadata = client["metadata"]
catalogDB = dbMetadata["catalog"]
datasetDB = dbMetadata["dataset"]
distributionDB = dbMetadata["distribution"]


# Define HealthDCAT-AP namespace with some properties
class HEALTHDCAT(DefinedNamespace):

    # FIXME: This is a placeholder until official HealthDCAT-AP namespace is defined
    _NS = Namespace("http://example.com/ns/healthdcat#")


class TREDataset(DCATDataset):
    model_config = ConfigDict(
                              json_schema_extra={
                                  "$ontology": "https://healthdcat-ap.github.io/",
                                  "$namespace": str(HEALTHDCAT),
                                  "$IRI": DCAT.Dataset,
                                  "$prefix": "healthdcatap"
                              }
                              )

    has_version: LiteralField = Field(
        description="This resource has a more specific, versioned resource",
        rdf_term=DCTERMS.hasVersion,
        rdf_type="rdfs_literal",
    )

    issued_date: LiteralField = Field(
        description="Date of issue of the resource",
        rdf_term=DCTERMS.issued,
        rdf_type="rdfs_literal",
    )

    modified_date: LiteralField = Field(
        description="Date of last modification of the resource",
        rdf_term=DCTERMS.modified,
        rdf_type="rdfs_literal",
    )


    @field_validator("has_version", mode="before")
    @classmethod
    def convert_to_literal(cls, value: Union[str, LiteralField]) -> List[LiteralField]:
        return force_literal_field(value)
    
    @field_validator("issued_date", "modified_date", mode="before")
    @classmethod
    def parse_issued_date(cls, value: Union[str, LiteralField]) -> List[LiteralField]:
        if isinstance(value, str) and len(value) == 10:
            # e.g., '2025-05-17'
            dt = datetime.strptime(value, "%Y-%m-%d")
            return LiteralField(value=dt.isoformat() + "Z", datatype=XSD.dateTime)
        elif isinstance(value, datetime):
            return LiteralField(value=value.isoformat() + "Z", datatype=XSD.dateTime)
        return value
    

class TREDistribution(DCATDistribution):

    media_type: LiteralField = Field(
        description="This resource has a more specific, versioned resource",
        rdf_term=DCAT.mediaType,
        rdf_type="rdfs_literal",
    )

    has_version: LiteralField = Field(
        description="This resource has a more specific, versioned resource",
        rdf_term=DCTERMS.hasVersion,
        rdf_type="rdfs_literal",
    )

    @field_validator("media_type", "has_version", mode="before")
    @classmethod
    def convert_to_literal(cls, value: Union[str, LiteralField]) -> List[LiteralField]:
        return force_literal_field(value)


def create_and_publish_metadata(dataset_info: Dict[str, Any], distributions_info: List[Dict[str, Any]]) -> None:

    # Prepare contact point if present
    contact_uri = None
    contact = None
    if "contact_point" in dataset_info and isinstance(dataset_info["contact_point"], list):
        contact_uri = URIRef(dataset_info["contact_point"])
        # Optionally, you can parse more contact info from JSON if available
        contact = VCard(
            hasEmail=[dataset_info.get("contact_email", "mailto:unknown@example.com")],
            full_name=[dataset_info.get("contact_name", "Unknown")],
            hasUID=dataset_info.get("contact_uid", "https://ror.org/")
        )

    publisher = Agent(name=[dataset_info.get("publisher.name", "BioData.pt")], identifier=dataset_info.get("publisher.identifier", "https://ror.org/02q7abn51"))

    # Prepare dataset definition
    dataset_definition = {
        "contact_point": [FDP_URI + "/tre/contact" + str(contact_uri)] if contact_uri else [],
        "description": [LiteralField(value=dataset_info["description"])],
        "distribution": dataset_info.get("distribution", []),
        "issued_date":LiteralField(value=datetime.strptime(dataset_info.get("issued_date", "2025-05-17"), "%Y-%m-%d").isoformat() + 'Z', datatype=XSD.dateTime),
        "modified_date": LiteralField(value=datetime.strptime(dataset_info.get("modified_date", "2024-05-17"), "%Y-%m-%d").isoformat() + 'Z', datatype=XSD.dateTime),
        "keyword": [LiteralField(value=kw) for kw in dataset_info.get("keywords", [])],
        "publisher": [publisher],
        "title": [LiteralField(value=dataset_info["title"])],
        "license": URIRef(dataset_info["license"]),
        "has_version": LiteralField(value=dataset_info.get("has_version", "1.0"))
    }

    dataset_subject = URIRef(FDP_URI + "/dataset/" + str(uuid.uuid4()))
    try:
        dataset = TREDataset(**dataset_definition)
    except ValidationError as e:
        print("Dataset validation error:", e)
        return

    dataset_graph = dataset.to_graph(dataset_subject)
    dataset_graph.add((dataset_subject, RDF.type, DCAT.Dataset))
    # Add theme if present
    if "theme" in dataset_info:
        theme = dataset_info["theme"]
        theme_uri = URIRef(theme["uri"])
        dataset_graph.add((dataset_subject, DCAT.theme, theme_uri))
        dataset_graph.add((theme_uri, RDF.type, SKOS.Concept))
        pref_labels = theme.get("prefLabel", {})
        for lang, label in pref_labels.items():
            dataset_graph.add((theme_uri, SKOS.prefLabel, Literal(label, lang=lang)))

        if "en" in pref_labels:
            dataset_graph.add((theme_uri, RDFS.label, Literal(pref_labels["en"])))


    # Add contact point if present
    if contact and contact_uri:
        contact_graph = contact.to_graph(contact_uri)
        dataset_graph += contact_graph

    fdp_parent_catalog = FDP_TRE_CATALOG_URI
    fdp_baseuri = FDP_URI
    fdp_user = FDP_ADMIN_USERNAME
    fdp_pass = FDP_ADMIN_PASSWORD

    fdpclient = fairclient.fdpclient.FDPClient(base_uri=fdp_baseuri, username=fdp_user, password=fdp_pass)


    # Upload dataset last, after distributions are created
    dataset_graph.add((dataset_subject, DCTERMS.isPartOf, URIRef(fdp_parent_catalog)))
    print(dataset_graph.serialize(format="turtle", encoding="utf-8").decode("utf-8"))
    new_dataset = fdpclient.create_and_publish("dataset", dataset_graph)
    print("Dataset FDP ID:", new_dataset)
    # Save dataset to MongoDB

    # Prepare and upload distributions
    distribution_fdp_ids = []
    for dist_info in distributions_info:
        distribution_subject = URIRef(FDP_URI + "/distribution/" + str(uuid.uuid4()))
        dist_definition = {
            "publisher": [publisher],
            "title": [LiteralField(value=dist_info["title"])],
            "description": [LiteralField(value=dist_info["description"])],
            "access_uri": [dist_info.get("access_uri", REMS_URI + "/catalogue")],
            "media_type": LiteralField(value=dist_info["media_type"]),
            "has_version": dist_info.get("has_version", "1.0"),
        }
        try:
            distribution = TREDistribution(**dist_definition)
        except ValidationError as e:
            print("Distribution validation error:", e)
            continue

        distribution_graph = distribution.to_graph(distribution_subject)
        # Add isPartOf link to dataset
        distribution_graph.add((distribution_subject, DCTERMS.isPartOf, new_dataset))
        # Upload distribution
        print(distribution_graph.serialize(format="turtle", encoding="utf-8").decode("utf-8"))
        distribution_fdp_id = fdpclient.create_and_publish(resource_type="distribution", metadata=distribution_graph)
        print("Distribution FDP ID:", distribution_fdp_id)
        # Save distribution to MongoDB

        distribution_fdp_ids.append(distribution_fdp_id)


    print("Distribution FDP IDs:", distribution_fdp_ids)
    return {"dataset_uri": new_dataset, "distribution_uri": distribution_fdp_ids}

