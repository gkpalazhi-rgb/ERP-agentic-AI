--
-- PostgreSQL database dump
--

\restrict 9UCioJ7hKLwvluqBWBLtUCOBQVXuRZo1Ue8FYdO2TlhAQpDGwvOpZJcbHb94h3f

-- Dumped from database version 15.17 (Homebrew)
-- Dumped by pg_dump version 15.17 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ai_conversations; Type: TABLE; Schema: public; Owner: adithyagopal
--

CREATE TABLE public.ai_conversations (
    id integer NOT NULL,
    user_id integer,
    user_query text,
    agent_response text,
    "timestamp" timestamp without time zone
);


ALTER TABLE public.ai_conversations OWNER TO adithyagopal;

--
-- Name: ai_conversations_id_seq; Type: SEQUENCE; Schema: public; Owner: adithyagopal
--

CREATE SEQUENCE public.ai_conversations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.ai_conversations_id_seq OWNER TO adithyagopal;

--
-- Name: ai_conversations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: adithyagopal
--

ALTER SEQUENCE public.ai_conversations_id_seq OWNED BY public.ai_conversations.id;


--
-- Name: erp_api_logs; Type: TABLE; Schema: public; Owner: adithyagopal
--

CREATE TABLE public.erp_api_logs (
    id integer NOT NULL,
    tool_name character varying,
    request_payload character varying,
    response_status character varying,
    called_at timestamp without time zone,
    plan_id character varying,
    step_index integer,
    "timestamp" timestamp without time zone
);


ALTER TABLE public.erp_api_logs OWNER TO adithyagopal;

--
-- Name: erp_api_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: adithyagopal
--

CREATE SEQUENCE public.erp_api_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.erp_api_logs_id_seq OWNER TO adithyagopal;

--
-- Name: erp_api_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: adithyagopal
--

ALTER SEQUENCE public.erp_api_logs_id_seq OWNED BY public.erp_api_logs.id;


--
-- Name: inventory; Type: TABLE; Schema: public; Owner: adithyagopal
--

CREATE TABLE public.inventory (
    id integer NOT NULL,
    item_name character varying,
    quantity integer,
    item_code character varying,
    category character varying
);


ALTER TABLE public.inventory OWNER TO adithyagopal;

--
-- Name: inventory_id_seq; Type: SEQUENCE; Schema: public; Owner: adithyagopal
--

CREATE SEQUENCE public.inventory_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.inventory_id_seq OWNER TO adithyagopal;

--
-- Name: inventory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: adithyagopal
--

ALTER SEQUENCE public.inventory_id_seq OWNED BY public.inventory.id;


--
-- Name: purchase_orders; Type: TABLE; Schema: public; Owner: adithyagopal
--

CREATE TABLE public.purchase_orders (
    id integer NOT NULL,
    item_name character varying,
    quantity integer,
    vendor character varying,
    created_at timestamp without time zone
);


ALTER TABLE public.purchase_orders OWNER TO adithyagopal;

--
-- Name: purchase_orders_id_seq; Type: SEQUENCE; Schema: public; Owner: adithyagopal
--

CREATE SEQUENCE public.purchase_orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.purchase_orders_id_seq OWNER TO adithyagopal;

--
-- Name: purchase_orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: adithyagopal
--

ALTER SEQUENCE public.purchase_orders_id_seq OWNED BY public.purchase_orders.id;


--
-- Name: vendors; Type: TABLE; Schema: public; Owner: adithyagopal
--

CREATE TABLE public.vendors (
    id integer NOT NULL,
    vendor_name character varying,
    item_name character varying,
    price double precision
);


ALTER TABLE public.vendors OWNER TO adithyagopal;

--
-- Name: vendors_id_seq; Type: SEQUENCE; Schema: public; Owner: adithyagopal
--

CREATE SEQUENCE public.vendors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.vendors_id_seq OWNER TO adithyagopal;

--
-- Name: vendors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: adithyagopal
--

ALTER SEQUENCE public.vendors_id_seq OWNED BY public.vendors.id;


--
-- Name: ai_conversations id; Type: DEFAULT; Schema: public; Owner: adithyagopal
--

ALTER TABLE ONLY public.ai_conversations ALTER COLUMN id SET DEFAULT nextval('public.ai_conversations_id_seq'::regclass);


--
-- Name: erp_api_logs id; Type: DEFAULT; Schema: public; Owner: adithyagopal
--

ALTER TABLE ONLY public.erp_api_logs ALTER COLUMN id SET DEFAULT nextval('public.erp_api_logs_id_seq'::regclass);


--
-- Name: inventory id; Type: DEFAULT; Schema: public; Owner: adithyagopal
--

ALTER TABLE ONLY public.inventory ALTER COLUMN id SET DEFAULT nextval('public.inventory_id_seq'::regclass);


--
-- Name: purchase_orders id; Type: DEFAULT; Schema: public; Owner: adithyagopal
--

ALTER TABLE ONLY public.purchase_orders ALTER COLUMN id SET DEFAULT nextval('public.purchase_orders_id_seq'::regclass);


--
-- Name: vendors id; Type: DEFAULT; Schema: public; Owner: adithyagopal
--

ALTER TABLE ONLY public.vendors ALTER COLUMN id SET DEFAULT nextval('public.vendors_id_seq'::regclass);


--
-- Data for Name: ai_conversations; Type: TABLE DATA; Schema: public; Owner: adithyagopal
--

COPY public.ai_conversations (id, user_id, user_query, agent_response, "timestamp") FROM stdin;
1	1	check laptop inventory	Inventory for laptop is 40 units.	2026-03-05 16:36:50.792648
2	1	check inventory for laptops	Inventory for laptops is 0 units.	2026-03-07 14:21:08.206279
3	1	check inventory for amber bottle	Inventory for amber bottle is 0 units.	2026-03-07 15:08:31.032184
4	1	check inventory for amber bottle	Inventory for amber bottle is 0 units.	2026-03-07 15:17:28.956602
5	1	check inventory for amber bottle	Purchase order created with ID 1.	2026-03-09 17:50:27.344557
\.


--
-- Data for Name: erp_api_logs; Type: TABLE DATA; Schema: public; Owner: adithyagopal
--

COPY public.erp_api_logs (id, tool_name, request_payload, response_status, called_at, plan_id, step_index, "timestamp") FROM stdin;
1	get_inventory	{'item': 'laptop'}	SUCCESS	2026-03-05 16:36:47.619672	\N	\N	\N
2	get_inventory	{'item': 'laptops'}	SUCCESS	2026-03-07 19:50:21.269714	\N	\N	2026-03-07 19:50:21.269765
3	get_inventory	{'item': 'amber bottle'}	SUCCESS	2026-03-07 20:37:39.576185	\N	\N	2026-03-07 20:37:39.576233
4	get_inventory	{'item': 'amber bottle'}	SUCCESS	2026-03-07 20:46:37.545504	\N	\N	2026-03-07 20:46:37.545565
5	get_inventory	{'item': 'amber bottle'}	SUCCESS	2026-03-09 23:19:43.638108	\N	\N	2026-03-09 23:19:43.638166
6	plan_execution	{'steps': [{'type': 'tool', 'name': 'get_inventory', 'args': {'item': 'amber bottle'}}]}	SUCCESS	2026-03-09 23:19:43.638108	\N	\N	2026-03-09 23:19:43.638166
\.


--
-- Data for Name: inventory; Type: TABLE DATA; Schema: public; Owner: adithyagopal
--

COPY public.inventory (id, item_name, quantity, item_code, category) FROM stdin;
2	10 ML RD DROPPER BOTTLE CLOSED NOZZLE WHITE CAP	80	PM03659	Packing Material
3	DHANWANTHARAM SOFT GEL CAPSULE	200	FG00639	Medicine
1	10 ML AMBER GLASS BOTTLE	10	PM03481	Packing Material
\.


--
-- Data for Name: purchase_orders; Type: TABLE DATA; Schema: public; Owner: adithyagopal
--

COPY public.purchase_orders (id, item_name, quantity, vendor, created_at) FROM stdin;
1	10 ML AMBER GLASS BOTTLE	100	default_vendor	2026-03-09 17:50:27.300663
\.


--
-- Data for Name: vendors; Type: TABLE DATA; Schema: public; Owner: adithyagopal
--

COPY public.vendors (id, vendor_name, item_name, price) FROM stdin;
\.


--
-- Name: ai_conversations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: adithyagopal
--

SELECT pg_catalog.setval('public.ai_conversations_id_seq', 5, true);


--
-- Name: erp_api_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: adithyagopal
--

SELECT pg_catalog.setval('public.erp_api_logs_id_seq', 6, true);


--
-- Name: inventory_id_seq; Type: SEQUENCE SET; Schema: public; Owner: adithyagopal
--

SELECT pg_catalog.setval('public.inventory_id_seq', 3, true);


--
-- Name: purchase_orders_id_seq; Type: SEQUENCE SET; Schema: public; Owner: adithyagopal
--

SELECT pg_catalog.setval('public.purchase_orders_id_seq', 1, true);


--
-- Name: vendors_id_seq; Type: SEQUENCE SET; Schema: public; Owner: adithyagopal
--

SELECT pg_catalog.setval('public.vendors_id_seq', 1, false);


--
-- Name: ai_conversations ai_conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: adithyagopal
--

ALTER TABLE ONLY public.ai_conversations
    ADD CONSTRAINT ai_conversations_pkey PRIMARY KEY (id);


--
-- Name: erp_api_logs erp_api_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: adithyagopal
--

ALTER TABLE ONLY public.erp_api_logs
    ADD CONSTRAINT erp_api_logs_pkey PRIMARY KEY (id);


--
-- Name: inventory inventory_pkey; Type: CONSTRAINT; Schema: public; Owner: adithyagopal
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_pkey PRIMARY KEY (id);


--
-- Name: purchase_orders purchase_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: adithyagopal
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_pkey PRIMARY KEY (id);


--
-- Name: vendors vendors_pkey; Type: CONSTRAINT; Schema: public; Owner: adithyagopal
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT vendors_pkey PRIMARY KEY (id);


--
-- Name: ix_ai_conversations_id; Type: INDEX; Schema: public; Owner: adithyagopal
--

CREATE INDEX ix_ai_conversations_id ON public.ai_conversations USING btree (id);


--
-- Name: ix_erp_api_logs_id; Type: INDEX; Schema: public; Owner: adithyagopal
--

CREATE INDEX ix_erp_api_logs_id ON public.erp_api_logs USING btree (id);


--
-- Name: ix_inventory_id; Type: INDEX; Schema: public; Owner: adithyagopal
--

CREATE INDEX ix_inventory_id ON public.inventory USING btree (id);


--
-- Name: ix_inventory_item_name; Type: INDEX; Schema: public; Owner: adithyagopal
--

CREATE UNIQUE INDEX ix_inventory_item_name ON public.inventory USING btree (item_name);


--
-- Name: ix_purchase_orders_id; Type: INDEX; Schema: public; Owner: adithyagopal
--

CREATE INDEX ix_purchase_orders_id ON public.purchase_orders USING btree (id);


--
-- Name: ix_vendors_id; Type: INDEX; Schema: public; Owner: adithyagopal
--

CREATE INDEX ix_vendors_id ON public.vendors USING btree (id);


--
-- PostgreSQL database dump complete
--

\unrestrict 9UCioJ7hKLwvluqBWBLtUCOBQVXuRZo1Ue8FYdO2TlhAQpDGwvOpZJcbHb94h3f

