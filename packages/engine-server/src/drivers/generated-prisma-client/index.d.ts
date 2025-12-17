
/**
 * Client
**/

import * as runtime from './runtime/library';
import $Types = runtime.Types // general types
import $Public = runtime.Types.Public
import $Utils = runtime.Types.Utils
import $Extensions = runtime.Types.Extensions

export type PrismaPromise<T> = $Public.PrismaPromise<T>


export type NotePayload<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
  name: "Note"
  objects: {
    vault: DVaultPayload<ExtArgs>
  }
  scalars: $Extensions.GetResult<{
    id: string
    fname: string | null
    title: string | null
    updated: number | null
    created: number | null
    stub: boolean | null
    dVaultId: number
  }, ExtArgs["result"]["note"]>
  composites: {}
}

/**
 * Model Note
 * 
 */
export type Note = runtime.Types.DefaultSelection<NotePayload>
export type DVaultPayload<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
  name: "DVault"
  objects: {
    workspace: WorkspacePayload<ExtArgs>
    Note: NotePayload<ExtArgs>[]
  }
  scalars: $Extensions.GetResult<{
    id: number
    name: string | null
    fsPath: string
    wsRoot: string
  }, ExtArgs["result"]["dVault"]>
  composites: {}
}

/**
 * Model DVault
 * 
 */
export type DVault = runtime.Types.DefaultSelection<DVaultPayload>
export type WorkspacePayload<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
  name: "Workspace"
  objects: {
    vaults: DVaultPayload<ExtArgs>[]
  }
  scalars: $Extensions.GetResult<{
    wsRoot: string
    prismaSchemaVersion: number
  }, ExtArgs["result"]["workspace"]>
  composites: {}
}

/**
 * Model Workspace
 * 
 */
export type Workspace = runtime.Types.DefaultSelection<WorkspacePayload>

/**
 * ##  Prisma Client ʲˢ
 * 
 * Type-safe database client for TypeScript & Node.js
 * @example
 * ```
 * const prisma = new PrismaClient()
 * // Fetch zero or more Notes
 * const notes = await prisma.note.findMany()
 * ```
 *
 * 
 * Read more in our [docs](https://www.prisma.io/docs/reference/tools-and-interfaces/prisma-client).
 */
export class PrismaClient<
  T extends Prisma.PrismaClientOptions = Prisma.PrismaClientOptions,
  U = 'log' extends keyof T ? T['log'] extends Array<Prisma.LogLevel | Prisma.LogDefinition> ? Prisma.GetEvents<T['log']> : never : never,
  GlobalReject extends Prisma.RejectOnNotFound | Prisma.RejectPerOperation | false | undefined = 'rejectOnNotFound' extends keyof T
    ? T['rejectOnNotFound']
    : false,
  ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs
> {
  [K: symbol]: { types: Prisma.TypeMap<ExtArgs>['other'] }

    /**
   * ##  Prisma Client ʲˢ
   * 
   * Type-safe database client for TypeScript & Node.js
   * @example
   * ```
   * const prisma = new PrismaClient()
   * // Fetch zero or more Notes
   * const notes = await prisma.note.findMany()
   * ```
   *
   * 
   * Read more in our [docs](https://www.prisma.io/docs/reference/tools-and-interfaces/prisma-client).
   */

  constructor(optionsArg ?: Prisma.Subset<T, Prisma.PrismaClientOptions>);
  $on<V extends (U | 'beforeExit')>(eventType: V, callback: (event: V extends 'query' ? Prisma.QueryEvent : V extends 'beforeExit' ? () => Promise<void> : Prisma.LogEvent) => void): void;

  /**
   * Connect with the database
   */
  $connect(): Promise<void>;

  /**
   * Disconnect from the database
   */
  $disconnect(): Promise<void>;

  /**
   * Add a middleware
   * @deprecated since 4.16.0. For new code, prefer client extensions instead.
   * @see https://pris.ly/d/extensions
   */
  $use(cb: Prisma.Middleware): void

/**
   * Executes a prepared raw query and returns the number of affected rows.
   * @example
   * ```
   * const result = await prisma.$executeRaw`UPDATE User SET cool = ${true} WHERE email = ${'user@email.com'};`
   * ```
   * 
   * Read more in our [docs](https://www.prisma.io/docs/reference/tools-and-interfaces/prisma-client/raw-database-access).
   */
  $executeRaw<T = unknown>(query: TemplateStringsArray | Prisma.Sql, ...values: any[]): Prisma.PrismaPromise<number>;

  /**
   * Executes a raw query and returns the number of affected rows.
   * Susceptible to SQL injections, see documentation.
   * @example
   * ```
   * const result = await prisma.$executeRawUnsafe('UPDATE User SET cool = $1 WHERE email = $2 ;', true, 'user@email.com')
   * ```
   * 
   * Read more in our [docs](https://www.prisma.io/docs/reference/tools-and-interfaces/prisma-client/raw-database-access).
   */
  $executeRawUnsafe<T = unknown>(query: string, ...values: any[]): Prisma.PrismaPromise<number>;

  /**
   * Performs a prepared raw query and returns the `SELECT` data.
   * @example
   * ```
   * const result = await prisma.$queryRaw`SELECT * FROM User WHERE id = ${1} OR email = ${'user@email.com'};`
   * ```
   * 
   * Read more in our [docs](https://www.prisma.io/docs/reference/tools-and-interfaces/prisma-client/raw-database-access).
   */
  $queryRaw<T = unknown>(query: TemplateStringsArray | Prisma.Sql, ...values: any[]): Prisma.PrismaPromise<T>;

  /**
   * Performs a raw query and returns the `SELECT` data.
   * Susceptible to SQL injections, see documentation.
   * @example
   * ```
   * const result = await prisma.$queryRawUnsafe('SELECT * FROM User WHERE id = $1 OR email = $2;', 1, 'user@email.com')
   * ```
   * 
   * Read more in our [docs](https://www.prisma.io/docs/reference/tools-and-interfaces/prisma-client/raw-database-access).
   */
  $queryRawUnsafe<T = unknown>(query: string, ...values: any[]): Prisma.PrismaPromise<T>;

  /**
   * Allows the running of a sequence of read/write operations that are guaranteed to either succeed or fail as a whole.
   * @example
   * ```
   * const [george, bob, alice] = await prisma.$transaction([
   *   prisma.user.create({ data: { name: 'George' } }),
   *   prisma.user.create({ data: { name: 'Bob' } }),
   *   prisma.user.create({ data: { name: 'Alice' } }),
   * ])
   * ```
   * 
   * Read more in our [docs](https://www.prisma.io/docs/concepts/components/prisma-client/transactions).
   */
  $transaction<P extends Prisma.PrismaPromise<any>[]>(arg: [...P], options?: { isolationLevel?: Prisma.TransactionIsolationLevel }): Promise<runtime.Types.Utils.UnwrapTuple<P>>

  $transaction<R>(fn: (prisma: Omit<PrismaClient, runtime.ITXClientDenyList>) => Promise<R>, options?: { maxWait?: number, timeout?: number, isolationLevel?: Prisma.TransactionIsolationLevel }): Promise<R>


  $extends: $Extensions.ExtendsHook<'extends', Prisma.TypeMapCb, ExtArgs>

      /**
   * `prisma.note`: Exposes CRUD operations for the **Note** model.
    * Example usage:
    * ```ts
    * // Fetch zero or more Notes
    * const notes = await prisma.note.findMany()
    * ```
    */
  get note(): Prisma.NoteDelegate<GlobalReject, ExtArgs>;

  /**
   * `prisma.dVault`: Exposes CRUD operations for the **DVault** model.
    * Example usage:
    * ```ts
    * // Fetch zero or more DVaults
    * const dVaults = await prisma.dVault.findMany()
    * ```
    */
  get dVault(): Prisma.DVaultDelegate<GlobalReject, ExtArgs>;

  /**
   * `prisma.workspace`: Exposes CRUD operations for the **Workspace** model.
    * Example usage:
    * ```ts
    * // Fetch zero or more Workspaces
    * const workspaces = await prisma.workspace.findMany()
    * ```
    */
  get workspace(): Prisma.WorkspaceDelegate<GlobalReject, ExtArgs>;
}

export namespace Prisma {
  export import DMMF = runtime.DMMF

  export type PrismaPromise<T> = $Public.PrismaPromise<T>

  /**
   * Validator
   */
  export import validator = runtime.Public.validator

  /**
   * Prisma Errors
   */
  export import PrismaClientKnownRequestError = runtime.PrismaClientKnownRequestError
  export import PrismaClientUnknownRequestError = runtime.PrismaClientUnknownRequestError
  export import PrismaClientRustPanicError = runtime.PrismaClientRustPanicError
  export import PrismaClientInitializationError = runtime.PrismaClientInitializationError
  export import PrismaClientValidationError = runtime.PrismaClientValidationError
  export import NotFoundError = runtime.NotFoundError

  /**
   * Re-export of sql-template-tag
   */
  export import sql = runtime.sqltag
  export import empty = runtime.empty
  export import join = runtime.join
  export import raw = runtime.raw
  export import Sql = runtime.Sql

  /**
   * Decimal.js
   */
  export import Decimal = runtime.Decimal

  export type DecimalJsLike = runtime.DecimalJsLike

  /**
   * Metrics 
   */
  export type Metrics = runtime.Metrics
  export type Metric<T> = runtime.Metric<T>
  export type MetricHistogram = runtime.MetricHistogram
  export type MetricHistogramBucket = runtime.MetricHistogramBucket

  /**
  * Extensions
  */
  export type Extension = $Extensions.UserArgs
  export import getExtensionContext = runtime.Extensions.getExtensionContext
  export type Args<T, F extends $Public.Operation> = $Public.Args<T, F>
  export type Payload<T, F extends $Public.Operation> = $Public.Payload<T, F>
  export type Result<T, A, F extends $Public.Operation> = $Public.Result<T, A, F>
  export type Exact<T, W> = $Public.Exact<T, W>

  /**
   * Prisma Client JS version: 4.16.2
   * Query Engine version: 4bc8b6e1b66cb932731fb1bdbbc550d1e010de81
   */
  export type PrismaVersion = {
    client: string
  }

  export const prismaVersion: PrismaVersion 

  /**
   * Utility Types
   */

  /**
   * From https://github.com/sindresorhus/type-fest/
   * Matches a JSON object.
   * This type can be useful to enforce some input to be JSON-compatible or as a super-type to be extended from. 
   */
  export type JsonObject = {[Key in string]?: JsonValue}

  /**
   * From https://github.com/sindresorhus/type-fest/
   * Matches a JSON array.
   */
  export interface JsonArray extends Array<JsonValue> {}

  /**
   * From https://github.com/sindresorhus/type-fest/
   * Matches any valid JSON value.
   */
  export type JsonValue = string | number | boolean | JsonObject | JsonArray | null

  /**
   * Matches a JSON object.
   * Unlike `JsonObject`, this type allows undefined and read-only properties.
   */
  export type InputJsonObject = {readonly [Key in string]?: InputJsonValue | null}

  /**
   * Matches a JSON array.
   * Unlike `JsonArray`, readonly arrays are assignable to this type.
   */
  export interface InputJsonArray extends ReadonlyArray<InputJsonValue | null> {}

  /**
   * Matches any valid value that can be used as an input for operations like
   * create and update as the value of a JSON field. Unlike `JsonValue`, this
   * type allows read-only arrays and read-only object properties and disallows
   * `null` at the top level.
   *
   * `null` cannot be used as the value of a JSON field because its meaning
   * would be ambiguous. Use `Prisma.JsonNull` to store the JSON null value or
   * `Prisma.DbNull` to clear the JSON value and set the field to the database
   * NULL value instead.
   *
   * @see https://www.prisma.io/docs/concepts/components/prisma-client/working-with-fields/working-with-json-fields#filtering-by-null-values
   */
  export type InputJsonValue = string | number | boolean | InputJsonObject | InputJsonArray

  /**
   * Types of the values used to represent different kinds of `null` values when working with JSON fields.
   * 
   * @see https://www.prisma.io/docs/concepts/components/prisma-client/working-with-fields/working-with-json-fields#filtering-on-a-json-field
   */
  namespace NullTypes {
    /**
    * Type of `Prisma.DbNull`.
    * 
    * You cannot use other instances of this class. Please use the `Prisma.DbNull` value.
    * 
    * @see https://www.prisma.io/docs/concepts/components/prisma-client/working-with-fields/working-with-json-fields#filtering-on-a-json-field
    */
    class DbNull {
      private DbNull: never
      private constructor()
    }

    /**
    * Type of `Prisma.JsonNull`.
    * 
    * You cannot use other instances of this class. Please use the `Prisma.JsonNull` value.
    * 
    * @see https://www.prisma.io/docs/concepts/components/prisma-client/working-with-fields/working-with-json-fields#filtering-on-a-json-field
    */
    class JsonNull {
      private JsonNull: never
      private constructor()
    }

    /**
    * Type of `Prisma.AnyNull`.
    * 
    * You cannot use other instances of this class. Please use the `Prisma.AnyNull` value.
    * 
    * @see https://www.prisma.io/docs/concepts/components/prisma-client/working-with-fields/working-with-json-fields#filtering-on-a-json-field
    */
    class AnyNull {
      private AnyNull: never
      private constructor()
    }
  }

  /**
   * Helper for filtering JSON entries that have `null` on the database (empty on the db)
   * 
   * @see https://www.prisma.io/docs/concepts/components/prisma-client/working-with-fields/working-with-json-fields#filtering-on-a-json-field
   */
  export const DbNull: NullTypes.DbNull

  /**
   * Helper for filtering JSON entries that have JSON `null` values (not empty on the db)
   * 
   * @see https://www.prisma.io/docs/concepts/components/prisma-client/working-with-fields/working-with-json-fields#filtering-on-a-json-field
   */
  export const JsonNull: NullTypes.JsonNull

  /**
   * Helper for filtering JSON entries that are `Prisma.DbNull` or `Prisma.JsonNull`
   * 
   * @see https://www.prisma.io/docs/concepts/components/prisma-client/working-with-fields/working-with-json-fields#filtering-on-a-json-field
   */
  export const AnyNull: NullTypes.AnyNull

  type SelectAndInclude = {
    select: any
    include: any
  }
  type HasSelect = {
    select: any
  }
  type HasInclude = {
    include: any
  }
  type CheckSelect<T, S, U> = T extends SelectAndInclude
    ? 'Please either choose `select` or `include`'
    : T extends HasSelect
    ? U
    : T extends HasInclude
    ? U
    : S

  /**
   * Get the type of the value, that the Promise holds.
   */
  export type PromiseType<T extends PromiseLike<any>> = T extends PromiseLike<infer U> ? U : T;

  /**
   * Get the return type of a function which returns a Promise.
   */
  export type PromiseReturnType<T extends (...args: any) => Promise<any>> = PromiseType<ReturnType<T>>

  /**
   * From T, pick a set of properties whose keys are in the union K
   */
  type Prisma__Pick<T, K extends keyof T> = {
      [P in K]: T[P];
  };


  export type Enumerable<T> = T | Array<T>;

  export type RequiredKeys<T> = {
    [K in keyof T]-?: {} extends Prisma__Pick<T, K> ? never : K
  }[keyof T]

  export type TruthyKeys<T> = keyof {
    [K in keyof T as T[K] extends false | undefined | null ? never : K]: K
  }

  export type TrueKeys<T> = TruthyKeys<Prisma__Pick<T, RequiredKeys<T>>>

  /**
   * Subset
   * @desc From `T` pick properties that exist in `U`. Simple version of Intersection
   */
  export type Subset<T, U> = {
    [key in keyof T]: key extends keyof U ? T[key] : never;
  };

  /**
   * SelectSubset
   * @desc From `T` pick properties that exist in `U`. Simple version of Intersection.
   * Additionally, it validates, if both select and include are present. If the case, it errors.
   */
  export type SelectSubset<T, U> = {
    [key in keyof T]: key extends keyof U ? T[key] : never
  } &
    (T extends SelectAndInclude
      ? 'Please either choose `select` or `include`.'
      : {})

  /**
   * Subset + Intersection
   * @desc From `T` pick properties that exist in `U` and intersect `K`
   */
  export type SubsetIntersection<T, U, K> = {
    [key in keyof T]: key extends keyof U ? T[key] : never
  } &
    K

  type Without<T, U> = { [P in Exclude<keyof T, keyof U>]?: never };

  /**
   * XOR is needed to have a real mutually exclusive union type
   * https://stackoverflow.com/questions/42123407/does-typescript-support-mutually-exclusive-types
   */
  type XOR<T, U> =
    T extends object ?
    U extends object ?
      (Without<T, U> & U) | (Without<U, T> & T)
    : U : T


  /**
   * Is T a Record?
   */
  type IsObject<T extends any> = T extends Array<any>
  ? False
  : T extends Date
  ? False
  : T extends Uint8Array
  ? False
  : T extends BigInt
  ? False
  : T extends object
  ? True
  : False


  /**
   * If it's T[], return T
   */
  export type UnEnumerate<T extends unknown> = T extends Array<infer U> ? U : T

  /**
   * From ts-toolbelt
   */

  type __Either<O extends object, K extends Key> = Omit<O, K> &
    {
      // Merge all but K
      [P in K]: Prisma__Pick<O, P & keyof O> // With K possibilities
    }[K]

  type EitherStrict<O extends object, K extends Key> = Strict<__Either<O, K>>

  type EitherLoose<O extends object, K extends Key> = ComputeRaw<__Either<O, K>>

  type _Either<
    O extends object,
    K extends Key,
    strict extends Boolean
  > = {
    1: EitherStrict<O, K>
    0: EitherLoose<O, K>
  }[strict]

  type Either<
    O extends object,
    K extends Key,
    strict extends Boolean = 1
  > = O extends unknown ? _Either<O, K, strict> : never

  export type Union = any

  type PatchUndefined<O extends object, O1 extends object> = {
    [K in keyof O]: O[K] extends undefined ? At<O1, K> : O[K]
  } & {}

  /** Helper Types for "Merge" **/
  export type IntersectOf<U extends Union> = (
    U extends unknown ? (k: U) => void : never
  ) extends (k: infer I) => void
    ? I
    : never

  export type Overwrite<O extends object, O1 extends object> = {
      [K in keyof O]: K extends keyof O1 ? O1[K] : O[K];
  } & {};

  type _Merge<U extends object> = IntersectOf<Overwrite<U, {
      [K in keyof U]-?: At<U, K>;
  }>>;

  type Key = string | number | symbol;
  type AtBasic<O extends object, K extends Key> = K extends keyof O ? O[K] : never;
  type AtStrict<O extends object, K extends Key> = O[K & keyof O];
  type AtLoose<O extends object, K extends Key> = O extends unknown ? AtStrict<O, K> : never;
  export type At<O extends object, K extends Key, strict extends Boolean = 1> = {
      1: AtStrict<O, K>;
      0: AtLoose<O, K>;
  }[strict];

  export type ComputeRaw<A extends any> = A extends Function ? A : {
    [K in keyof A]: A[K];
  } & {};

  export type OptionalFlat<O> = {
    [K in keyof O]?: O[K];
  } & {};

  type _Record<K extends keyof any, T> = {
    [P in K]: T;
  };

  // cause typescript not to expand types and preserve names
  type NoExpand<T> = T extends unknown ? T : never;

  // this type assumes the passed object is entirely optional
  type AtLeast<O extends object, K extends string> = NoExpand<
    O extends unknown
    ? | (K extends keyof O ? { [P in K]: O[P] } & O : O)
      | {[P in keyof O as P extends K ? K : never]-?: O[P]} & O
    : never>;

  type _Strict<U, _U = U> = U extends unknown ? U & OptionalFlat<_Record<Exclude<Keys<_U>, keyof U>, never>> : never;

  export type Strict<U extends object> = ComputeRaw<_Strict<U>>;
  /** End Helper Types for "Merge" **/

  export type Merge<U extends object> = ComputeRaw<_Merge<Strict<U>>>;

  /**
  A [[Boolean]]
  */
  export type Boolean = True | False

  // /**
  // 1
  // */
  export type True = 1

  /**
  0
  */
  export type False = 0

  export type Not<B extends Boolean> = {
    0: 1
    1: 0
  }[B]

  export type Extends<A1 extends any, A2 extends any> = [A1] extends [never]
    ? 0 // anything `never` is false
    : A1 extends A2
    ? 1
    : 0

  export type Has<U extends Union, U1 extends Union> = Not<
    Extends<Exclude<U1, U>, U1>
  >

  export type Or<B1 extends Boolean, B2 extends Boolean> = {
    0: {
      0: 0
      1: 1
    }
    1: {
      0: 1
      1: 1
    }
  }[B1][B2]

  export type Keys<U extends Union> = U extends unknown ? keyof U : never

  type Cast<A, B> = A extends B ? A : B;

  export const type: unique symbol;



  /**
   * Used by group by
   */

  export type GetScalarType<T, O> = O extends object ? {
    [P in keyof T]: P extends keyof O
      ? O[P]
      : never
  } : never

  type FieldPaths<
    T,
    U = Omit<T, '_avg' | '_sum' | '_count' | '_min' | '_max'>
  > = IsObject<T> extends True ? U : T

  type GetHavingFields<T> = {
    [K in keyof T]: Or<
      Or<Extends<'OR', K>, Extends<'AND', K>>,
      Extends<'NOT', K>
    > extends True
      ? // infer is only needed to not hit TS limit
        // based on the brilliant idea of Pierre-Antoine Mills
        // https://github.com/microsoft/TypeScript/issues/30188#issuecomment-478938437
        T[K] extends infer TK
        ? GetHavingFields<UnEnumerate<TK> extends object ? Merge<UnEnumerate<TK>> : never>
        : never
      : {} extends FieldPaths<T[K]>
      ? never
      : K
  }[keyof T]

  /**
   * Convert tuple to union
   */
  type _TupleToUnion<T> = T extends (infer E)[] ? E : never
  type TupleToUnion<K extends readonly any[]> = _TupleToUnion<K>
  type MaybeTupleToUnion<T> = T extends any[] ? TupleToUnion<T> : T

  /**
   * Like `Pick`, but with an array
   */
  type PickArray<T, K extends Array<keyof T>> = Prisma__Pick<T, TupleToUnion<K>>

  /**
   * Exclude all keys with underscores
   */
  type ExcludeUnderscoreKeys<T extends string> = T extends `_${string}` ? never : T


  export type FieldRef<Model, FieldType> = runtime.FieldRef<Model, FieldType>

  type FieldRefInputType<Model, FieldType> = Model extends never ? never : FieldRef<Model, FieldType>


  export const ModelName: {
    Note: 'Note',
    DVault: 'DVault',
    Workspace: 'Workspace'
  };

  export type ModelName = (typeof ModelName)[keyof typeof ModelName]


  export type Datasources = {
    db?: Datasource
  }


  interface TypeMapCb extends $Utils.Fn<{extArgs: $Extensions.Args}, $Utils.Record<string, any>> {
    returns: Prisma.TypeMap<this['params']['extArgs']>
  }

  export type TypeMap<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    meta: {
      modelProps: 'note' | 'dVault' | 'workspace'
      txIsolationLevel: Prisma.TransactionIsolationLevel
    },
    model: {
      Note: {
        payload: NotePayload<ExtArgs>
        operations: {
          findUnique: {
            args: Prisma.NoteFindUniqueArgs<ExtArgs>,
            result: $Utils.PayloadToResult<NotePayload> | null
          }
          findUniqueOrThrow: {
            args: Prisma.NoteFindUniqueOrThrowArgs<ExtArgs>,
            result: $Utils.PayloadToResult<NotePayload>
          }
          findFirst: {
            args: Prisma.NoteFindFirstArgs<ExtArgs>,
            result: $Utils.PayloadToResult<NotePayload> | null
          }
          findFirstOrThrow: {
            args: Prisma.NoteFindFirstOrThrowArgs<ExtArgs>,
            result: $Utils.PayloadToResult<NotePayload>
          }
          findMany: {
            args: Prisma.NoteFindManyArgs<ExtArgs>,
            result: $Utils.PayloadToResult<NotePayload>[]
          }
          create: {
            args: Prisma.NoteCreateArgs<ExtArgs>,
            result: $Utils.PayloadToResult<NotePayload>
          }
          delete: {
            args: Prisma.NoteDeleteArgs<ExtArgs>,
            result: $Utils.PayloadToResult<NotePayload>
          }
          update: {
            args: Prisma.NoteUpdateArgs<ExtArgs>,
            result: $Utils.PayloadToResult<NotePayload>
          }
          deleteMany: {
            args: Prisma.NoteDeleteManyArgs<ExtArgs>,
            result: Prisma.BatchPayload
          }
          updateMany: {
            args: Prisma.NoteUpdateManyArgs<ExtArgs>,
            result: Prisma.BatchPayload
          }
          upsert: {
            args: Prisma.NoteUpsertArgs<ExtArgs>,
            result: $Utils.PayloadToResult<NotePayload>
          }
          aggregate: {
            args: Prisma.NoteAggregateArgs<ExtArgs>,
            result: $Utils.Optional<AggregateNote>
          }
          groupBy: {
            args: Prisma.NoteGroupByArgs<ExtArgs>,
            result: $Utils.Optional<NoteGroupByOutputType>[]
          }
          count: {
            args: Prisma.NoteCountArgs<ExtArgs>,
            result: $Utils.Optional<NoteCountAggregateOutputType> | number
          }
        }
      }
      DVault: {
        payload: DVaultPayload<ExtArgs>
        operations: {
          findUnique: {
            args: Prisma.DVaultFindUniqueArgs<ExtArgs>,
            result: $Utils.PayloadToResult<DVaultPayload> | null
          }
          findUniqueOrThrow: {
            args: Prisma.DVaultFindUniqueOrThrowArgs<ExtArgs>,
            result: $Utils.PayloadToResult<DVaultPayload>
          }
          findFirst: {
            args: Prisma.DVaultFindFirstArgs<ExtArgs>,
            result: $Utils.PayloadToResult<DVaultPayload> | null
          }
          findFirstOrThrow: {
            args: Prisma.DVaultFindFirstOrThrowArgs<ExtArgs>,
            result: $Utils.PayloadToResult<DVaultPayload>
          }
          findMany: {
            args: Prisma.DVaultFindManyArgs<ExtArgs>,
            result: $Utils.PayloadToResult<DVaultPayload>[]
          }
          create: {
            args: Prisma.DVaultCreateArgs<ExtArgs>,
            result: $Utils.PayloadToResult<DVaultPayload>
          }
          delete: {
            args: Prisma.DVaultDeleteArgs<ExtArgs>,
            result: $Utils.PayloadToResult<DVaultPayload>
          }
          update: {
            args: Prisma.DVaultUpdateArgs<ExtArgs>,
            result: $Utils.PayloadToResult<DVaultPayload>
          }
          deleteMany: {
            args: Prisma.DVaultDeleteManyArgs<ExtArgs>,
            result: Prisma.BatchPayload
          }
          updateMany: {
            args: Prisma.DVaultUpdateManyArgs<ExtArgs>,
            result: Prisma.BatchPayload
          }
          upsert: {
            args: Prisma.DVaultUpsertArgs<ExtArgs>,
            result: $Utils.PayloadToResult<DVaultPayload>
          }
          aggregate: {
            args: Prisma.DVaultAggregateArgs<ExtArgs>,
            result: $Utils.Optional<AggregateDVault>
          }
          groupBy: {
            args: Prisma.DVaultGroupByArgs<ExtArgs>,
            result: $Utils.Optional<DVaultGroupByOutputType>[]
          }
          count: {
            args: Prisma.DVaultCountArgs<ExtArgs>,
            result: $Utils.Optional<DVaultCountAggregateOutputType> | number
          }
        }
      }
      Workspace: {
        payload: WorkspacePayload<ExtArgs>
        operations: {
          findUnique: {
            args: Prisma.WorkspaceFindUniqueArgs<ExtArgs>,
            result: $Utils.PayloadToResult<WorkspacePayload> | null
          }
          findUniqueOrThrow: {
            args: Prisma.WorkspaceFindUniqueOrThrowArgs<ExtArgs>,
            result: $Utils.PayloadToResult<WorkspacePayload>
          }
          findFirst: {
            args: Prisma.WorkspaceFindFirstArgs<ExtArgs>,
            result: $Utils.PayloadToResult<WorkspacePayload> | null
          }
          findFirstOrThrow: {
            args: Prisma.WorkspaceFindFirstOrThrowArgs<ExtArgs>,
            result: $Utils.PayloadToResult<WorkspacePayload>
          }
          findMany: {
            args: Prisma.WorkspaceFindManyArgs<ExtArgs>,
            result: $Utils.PayloadToResult<WorkspacePayload>[]
          }
          create: {
            args: Prisma.WorkspaceCreateArgs<ExtArgs>,
            result: $Utils.PayloadToResult<WorkspacePayload>
          }
          delete: {
            args: Prisma.WorkspaceDeleteArgs<ExtArgs>,
            result: $Utils.PayloadToResult<WorkspacePayload>
          }
          update: {
            args: Prisma.WorkspaceUpdateArgs<ExtArgs>,
            result: $Utils.PayloadToResult<WorkspacePayload>
          }
          deleteMany: {
            args: Prisma.WorkspaceDeleteManyArgs<ExtArgs>,
            result: Prisma.BatchPayload
          }
          updateMany: {
            args: Prisma.WorkspaceUpdateManyArgs<ExtArgs>,
            result: Prisma.BatchPayload
          }
          upsert: {
            args: Prisma.WorkspaceUpsertArgs<ExtArgs>,
            result: $Utils.PayloadToResult<WorkspacePayload>
          }
          aggregate: {
            args: Prisma.WorkspaceAggregateArgs<ExtArgs>,
            result: $Utils.Optional<AggregateWorkspace>
          }
          groupBy: {
            args: Prisma.WorkspaceGroupByArgs<ExtArgs>,
            result: $Utils.Optional<WorkspaceGroupByOutputType>[]
          }
          count: {
            args: Prisma.WorkspaceCountArgs<ExtArgs>,
            result: $Utils.Optional<WorkspaceCountAggregateOutputType> | number
          }
        }
      }
    }
  } & {
    other: {
      payload: any
      operations: {
        $executeRawUnsafe: {
          args: [query: string, ...values: any[]],
          result: any
        }
        $executeRaw: {
          args: [query: TemplateStringsArray | Prisma.Sql, ...values: any[]],
          result: any
        }
        $queryRawUnsafe: {
          args: [query: string, ...values: any[]],
          result: any
        }
        $queryRaw: {
          args: [query: TemplateStringsArray | Prisma.Sql, ...values: any[]],
          result: any
        }
      }
    }
  }
  export const defineExtension: $Extensions.ExtendsHook<'define', Prisma.TypeMapCb, $Extensions.DefaultArgs>
  export type DefaultPrismaClient = PrismaClient
  export type RejectOnNotFound = boolean | ((error: Error) => Error)
  export type RejectPerModel = { [P in ModelName]?: RejectOnNotFound }
  export type RejectPerOperation =  { [P in "findUnique" | "findFirst"]?: RejectPerModel | RejectOnNotFound } 
  type IsReject<T> = T extends true ? True : T extends (err: Error) => Error ? True : False
  export type HasReject<
    GlobalRejectSettings extends Prisma.PrismaClientOptions['rejectOnNotFound'],
    LocalRejectSettings,
    Action extends PrismaAction,
    Model extends ModelName
  > = LocalRejectSettings extends RejectOnNotFound
    ? IsReject<LocalRejectSettings>
    : GlobalRejectSettings extends RejectPerOperation
    ? Action extends keyof GlobalRejectSettings
      ? GlobalRejectSettings[Action] extends RejectOnNotFound
        ? IsReject<GlobalRejectSettings[Action]>
        : GlobalRejectSettings[Action] extends RejectPerModel
        ? Model extends keyof GlobalRejectSettings[Action]
          ? IsReject<GlobalRejectSettings[Action][Model]>
          : False
        : False
      : False
    : IsReject<GlobalRejectSettings>
  export type ErrorFormat = 'pretty' | 'colorless' | 'minimal'

  export interface PrismaClientOptions {
    /**
     * Configure findUnique/findFirst to throw an error if the query returns null. 
     * @deprecated since 4.0.0. Use `findUniqueOrThrow`/`findFirstOrThrow` methods instead.
     * @example
     * ```
     * // Reject on both findUnique/findFirst
     * rejectOnNotFound: true
     * // Reject only on findFirst with a custom error
     * rejectOnNotFound: { findFirst: (err) => new Error("Custom Error")}
     * // Reject on user.findUnique with a custom error
     * rejectOnNotFound: { findUnique: {User: (err) => new Error("User not found")}}
     * ```
     */
    rejectOnNotFound?: RejectOnNotFound | RejectPerOperation
    /**
     * Overwrites the datasource url from your schema.prisma file
     */
    datasources?: Datasources

    /**
     * @default "colorless"
     */
    errorFormat?: ErrorFormat

    /**
     * @example
     * ```
     * // Defaults to stdout
     * log: ['query', 'info', 'warn', 'error']
     * 
     * // Emit as events
     * log: [
     *  { emit: 'stdout', level: 'query' },
     *  { emit: 'stdout', level: 'info' },
     *  { emit: 'stdout', level: 'warn' }
     *  { emit: 'stdout', level: 'error' }
     * ]
     * ```
     * Read more in our [docs](https://www.prisma.io/docs/reference/tools-and-interfaces/prisma-client/logging#the-log-option).
     */
    log?: Array<LogLevel | LogDefinition>
  }

  /* Types for Logging */
  export type LogLevel = 'info' | 'query' | 'warn' | 'error'
  export type LogDefinition = {
    level: LogLevel
    emit: 'stdout' | 'event'
  }

  export type GetLogType<T extends LogLevel | LogDefinition> = T extends LogDefinition ? T['emit'] extends 'event' ? T['level'] : never : never
  export type GetEvents<T extends any> = T extends Array<LogLevel | LogDefinition> ?
    GetLogType<T[0]> | GetLogType<T[1]> | GetLogType<T[2]> | GetLogType<T[3]>
    : never

  export type QueryEvent = {
    timestamp: Date
    query: string
    params: string
    duration: number
    target: string
  }

  export type LogEvent = {
    timestamp: Date
    message: string
    target: string
  }
  /* End Types for Logging */


  export type PrismaAction =
    | 'findUnique'
    | 'findMany'
    | 'findFirst'
    | 'create'
    | 'createMany'
    | 'update'
    | 'updateMany'
    | 'upsert'
    | 'delete'
    | 'deleteMany'
    | 'executeRaw'
    | 'queryRaw'
    | 'aggregate'
    | 'count'
    | 'runCommandRaw'
    | 'findRaw'

  /**
   * These options are being passed into the middleware as "params"
   */
  export type MiddlewareParams = {
    model?: ModelName
    action: PrismaAction
    args: any
    dataPath: string[]
    runInTransaction: boolean
  }

  /**
   * The `T` type makes sure, that the `return proceed` is not forgotten in the middleware implementation
   */
  export type Middleware<T = any> = (
    params: MiddlewareParams,
    next: (params: MiddlewareParams) => Promise<T>,
  ) => Promise<T>

  // tested in getLogLevel.test.ts
  export function getLogLevel(log: Array<LogLevel | LogDefinition>): LogLevel | undefined;

  /**
   * `PrismaClient` proxy available in interactive transactions.
   */
  export type TransactionClient = Omit<Prisma.DefaultPrismaClient, runtime.ITXClientDenyList>

  export type Datasource = {
    url?: string
  }

  /**
   * Count Types
   */


  /**
   * Count Type DVaultCountOutputType
   */


  export type DVaultCountOutputType = {
    Note: number
  }

  export type DVaultCountOutputTypeSelect<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    Note?: boolean | DVaultCountOutputTypeCountNoteArgs
  }

  // Custom InputTypes

  /**
   * DVaultCountOutputType without action
   */
  export type DVaultCountOutputTypeArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the DVaultCountOutputType
     */
    select?: DVaultCountOutputTypeSelect<ExtArgs> | null
  }


  /**
   * DVaultCountOutputType without action
   */
  export type DVaultCountOutputTypeCountNoteArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    where?: NoteWhereInput
  }



  /**
   * Count Type WorkspaceCountOutputType
   */


  export type WorkspaceCountOutputType = {
    vaults: number
  }

  export type WorkspaceCountOutputTypeSelect<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    vaults?: boolean | WorkspaceCountOutputTypeCountVaultsArgs
  }

  // Custom InputTypes

  /**
   * WorkspaceCountOutputType without action
   */
  export type WorkspaceCountOutputTypeArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the WorkspaceCountOutputType
     */
    select?: WorkspaceCountOutputTypeSelect<ExtArgs> | null
  }


  /**
   * WorkspaceCountOutputType without action
   */
  export type WorkspaceCountOutputTypeCountVaultsArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    where?: DVaultWhereInput
  }



  /**
   * Models
   */

  /**
   * Model Note
   */


  export type AggregateNote = {
    _count: NoteCountAggregateOutputType | null
    _avg: NoteAvgAggregateOutputType | null
    _sum: NoteSumAggregateOutputType | null
    _min: NoteMinAggregateOutputType | null
    _max: NoteMaxAggregateOutputType | null
  }

  export type NoteAvgAggregateOutputType = {
    updated: number | null
    created: number | null
    dVaultId: number | null
  }

  export type NoteSumAggregateOutputType = {
    updated: number | null
    created: number | null
    dVaultId: number | null
  }

  export type NoteMinAggregateOutputType = {
    id: string | null
    fname: string | null
    title: string | null
    updated: number | null
    created: number | null
    stub: boolean | null
    dVaultId: number | null
  }

  export type NoteMaxAggregateOutputType = {
    id: string | null
    fname: string | null
    title: string | null
    updated: number | null
    created: number | null
    stub: boolean | null
    dVaultId: number | null
  }

  export type NoteCountAggregateOutputType = {
    id: number
    fname: number
    title: number
    updated: number
    created: number
    stub: number
    dVaultId: number
    _all: number
  }


  export type NoteAvgAggregateInputType = {
    updated?: true
    created?: true
    dVaultId?: true
  }

  export type NoteSumAggregateInputType = {
    updated?: true
    created?: true
    dVaultId?: true
  }

  export type NoteMinAggregateInputType = {
    id?: true
    fname?: true
    title?: true
    updated?: true
    created?: true
    stub?: true
    dVaultId?: true
  }

  export type NoteMaxAggregateInputType = {
    id?: true
    fname?: true
    title?: true
    updated?: true
    created?: true
    stub?: true
    dVaultId?: true
  }

  export type NoteCountAggregateInputType = {
    id?: true
    fname?: true
    title?: true
    updated?: true
    created?: true
    stub?: true
    dVaultId?: true
    _all?: true
  }

  export type NoteAggregateArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Filter which Note to aggregate.
     */
    where?: NoteWhereInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/sorting Sorting Docs}
     * 
     * Determine the order of Notes to fetch.
     */
    orderBy?: Enumerable<NoteOrderByWithRelationInput>
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination#cursor-based-pagination Cursor Docs}
     * 
     * Sets the start position
     */
    cursor?: NoteWhereUniqueInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Take `±n` Notes from the position of the cursor.
     */
    take?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Skip the first `n` Notes.
     */
    skip?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/aggregations Aggregation Docs}
     * 
     * Count returned Notes
    **/
    _count?: true | NoteCountAggregateInputType
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/aggregations Aggregation Docs}
     * 
     * Select which fields to average
    **/
    _avg?: NoteAvgAggregateInputType
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/aggregations Aggregation Docs}
     * 
     * Select which fields to sum
    **/
    _sum?: NoteSumAggregateInputType
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/aggregations Aggregation Docs}
     * 
     * Select which fields to find the minimum value
    **/
    _min?: NoteMinAggregateInputType
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/aggregations Aggregation Docs}
     * 
     * Select which fields to find the maximum value
    **/
    _max?: NoteMaxAggregateInputType
  }

  export type GetNoteAggregateType<T extends NoteAggregateArgs> = {
        [P in keyof T & keyof AggregateNote]: P extends '_count' | 'count'
      ? T[P] extends true
        ? number
        : GetScalarType<T[P], AggregateNote[P]>
      : GetScalarType<T[P], AggregateNote[P]>
  }




  export type NoteGroupByArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    where?: NoteWhereInput
    orderBy?: Enumerable<NoteOrderByWithAggregationInput>
    by: NoteScalarFieldEnum[]
    having?: NoteScalarWhereWithAggregatesInput
    take?: number
    skip?: number
    _count?: NoteCountAggregateInputType | true
    _avg?: NoteAvgAggregateInputType
    _sum?: NoteSumAggregateInputType
    _min?: NoteMinAggregateInputType
    _max?: NoteMaxAggregateInputType
  }


  export type NoteGroupByOutputType = {
    id: string
    fname: string | null
    title: string | null
    updated: number | null
    created: number | null
    stub: boolean | null
    dVaultId: number
    _count: NoteCountAggregateOutputType | null
    _avg: NoteAvgAggregateOutputType | null
    _sum: NoteSumAggregateOutputType | null
    _min: NoteMinAggregateOutputType | null
    _max: NoteMaxAggregateOutputType | null
  }

  type GetNoteGroupByPayload<T extends NoteGroupByArgs> = Prisma.PrismaPromise<
    Array<
      PickArray<NoteGroupByOutputType, T['by']> &
        {
          [P in ((keyof T) & (keyof NoteGroupByOutputType))]: P extends '_count'
            ? T[P] extends boolean
              ? number
              : GetScalarType<T[P], NoteGroupByOutputType[P]>
            : GetScalarType<T[P], NoteGroupByOutputType[P]>
        }
      >
    >


  export type NoteSelect<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = $Extensions.GetSelect<{
    id?: boolean
    fname?: boolean
    title?: boolean
    updated?: boolean
    created?: boolean
    stub?: boolean
    dVaultId?: boolean
    vault?: boolean | DVaultArgs<ExtArgs>
  }, ExtArgs["result"]["note"]>

  export type NoteSelectScalar = {
    id?: boolean
    fname?: boolean
    title?: boolean
    updated?: boolean
    created?: boolean
    stub?: boolean
    dVaultId?: boolean
  }

  export type NoteInclude<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    vault?: boolean | DVaultArgs<ExtArgs>
  }


  type NoteGetPayload<S extends boolean | null | undefined | NoteArgs> = $Types.GetResult<NotePayload, S>

  type NoteCountArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = 
    Omit<NoteFindManyArgs, 'select' | 'include'> & {
      select?: NoteCountAggregateInputType | true
    }

  export interface NoteDelegate<GlobalRejectSettings extends Prisma.RejectOnNotFound | Prisma.RejectPerOperation | false | undefined, ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> {
    [K: symbol]: { types: Prisma.TypeMap<ExtArgs>['model']['Note'], meta: { name: 'Note' } }
    /**
     * Find zero or one Note that matches the filter.
     * @param {NoteFindUniqueArgs} args - Arguments to find a Note
     * @example
     * // Get one Note
     * const note = await prisma.note.findUnique({
     *   where: {
     *     // ... provide filter here
     *   }
     * })
    **/
    findUnique<T extends NoteFindUniqueArgs<ExtArgs>, LocalRejectSettings = T["rejectOnNotFound"] extends RejectOnNotFound ? T['rejectOnNotFound'] : undefined>(
      args: SelectSubset<T, NoteFindUniqueArgs<ExtArgs>>
    ): HasReject<GlobalRejectSettings, LocalRejectSettings, 'findUnique', 'Note'> extends True ? Prisma__NoteClient<$Types.GetResult<NotePayload<ExtArgs>, T, 'findUnique', never>, never, ExtArgs> : Prisma__NoteClient<$Types.GetResult<NotePayload<ExtArgs>, T, 'findUnique', never> | null, null, ExtArgs>

    /**
     * Find one Note that matches the filter or throw an error  with `error.code='P2025'` 
     *     if no matches were found.
     * @param {NoteFindUniqueOrThrowArgs} args - Arguments to find a Note
     * @example
     * // Get one Note
     * const note = await prisma.note.findUniqueOrThrow({
     *   where: {
     *     // ... provide filter here
     *   }
     * })
    **/
    findUniqueOrThrow<T extends NoteFindUniqueOrThrowArgs<ExtArgs>>(
      args?: SelectSubset<T, NoteFindUniqueOrThrowArgs<ExtArgs>>
    ): Prisma__NoteClient<$Types.GetResult<NotePayload<ExtArgs>, T, 'findUniqueOrThrow', never>, never, ExtArgs>

    /**
     * Find the first Note that matches the filter.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {NoteFindFirstArgs} args - Arguments to find a Note
     * @example
     * // Get one Note
     * const note = await prisma.note.findFirst({
     *   where: {
     *     // ... provide filter here
     *   }
     * })
    **/
    findFirst<T extends NoteFindFirstArgs<ExtArgs>, LocalRejectSettings = T["rejectOnNotFound"] extends RejectOnNotFound ? T['rejectOnNotFound'] : undefined>(
      args?: SelectSubset<T, NoteFindFirstArgs<ExtArgs>>
    ): HasReject<GlobalRejectSettings, LocalRejectSettings, 'findFirst', 'Note'> extends True ? Prisma__NoteClient<$Types.GetResult<NotePayload<ExtArgs>, T, 'findFirst', never>, never, ExtArgs> : Prisma__NoteClient<$Types.GetResult<NotePayload<ExtArgs>, T, 'findFirst', never> | null, null, ExtArgs>

    /**
     * Find the first Note that matches the filter or
     * throw `NotFoundError` if no matches were found.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {NoteFindFirstOrThrowArgs} args - Arguments to find a Note
     * @example
     * // Get one Note
     * const note = await prisma.note.findFirstOrThrow({
     *   where: {
     *     // ... provide filter here
     *   }
     * })
    **/
    findFirstOrThrow<T extends NoteFindFirstOrThrowArgs<ExtArgs>>(
      args?: SelectSubset<T, NoteFindFirstOrThrowArgs<ExtArgs>>
    ): Prisma__NoteClient<$Types.GetResult<NotePayload<ExtArgs>, T, 'findFirstOrThrow', never>, never, ExtArgs>

    /**
     * Find zero or more Notes that matches the filter.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {NoteFindManyArgs=} args - Arguments to filter and select certain fields only.
     * @example
     * // Get all Notes
     * const notes = await prisma.note.findMany()
     * 
     * // Get first 10 Notes
     * const notes = await prisma.note.findMany({ take: 10 })
     * 
     * // Only select the `id`
     * const noteWithIdOnly = await prisma.note.findMany({ select: { id: true } })
     * 
    **/
    findMany<T extends NoteFindManyArgs<ExtArgs>>(
      args?: SelectSubset<T, NoteFindManyArgs<ExtArgs>>
    ): Prisma.PrismaPromise<$Types.GetResult<NotePayload<ExtArgs>, T, 'findMany', never>>

    /**
     * Create a Note.
     * @param {NoteCreateArgs} args - Arguments to create a Note.
     * @example
     * // Create one Note
     * const Note = await prisma.note.create({
     *   data: {
     *     // ... data to create a Note
     *   }
     * })
     * 
    **/
    create<T extends NoteCreateArgs<ExtArgs>>(
      args: SelectSubset<T, NoteCreateArgs<ExtArgs>>
    ): Prisma__NoteClient<$Types.GetResult<NotePayload<ExtArgs>, T, 'create', never>, never, ExtArgs>

    /**
     * Delete a Note.
     * @param {NoteDeleteArgs} args - Arguments to delete one Note.
     * @example
     * // Delete one Note
     * const Note = await prisma.note.delete({
     *   where: {
     *     // ... filter to delete one Note
     *   }
     * })
     * 
    **/
    delete<T extends NoteDeleteArgs<ExtArgs>>(
      args: SelectSubset<T, NoteDeleteArgs<ExtArgs>>
    ): Prisma__NoteClient<$Types.GetResult<NotePayload<ExtArgs>, T, 'delete', never>, never, ExtArgs>

    /**
     * Update one Note.
     * @param {NoteUpdateArgs} args - Arguments to update one Note.
     * @example
     * // Update one Note
     * const note = await prisma.note.update({
     *   where: {
     *     // ... provide filter here
     *   },
     *   data: {
     *     // ... provide data here
     *   }
     * })
     * 
    **/
    update<T extends NoteUpdateArgs<ExtArgs>>(
      args: SelectSubset<T, NoteUpdateArgs<ExtArgs>>
    ): Prisma__NoteClient<$Types.GetResult<NotePayload<ExtArgs>, T, 'update', never>, never, ExtArgs>

    /**
     * Delete zero or more Notes.
     * @param {NoteDeleteManyArgs} args - Arguments to filter Notes to delete.
     * @example
     * // Delete a few Notes
     * const { count } = await prisma.note.deleteMany({
     *   where: {
     *     // ... provide filter here
     *   }
     * })
     * 
    **/
    deleteMany<T extends NoteDeleteManyArgs<ExtArgs>>(
      args?: SelectSubset<T, NoteDeleteManyArgs<ExtArgs>>
    ): Prisma.PrismaPromise<BatchPayload>

    /**
     * Update zero or more Notes.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {NoteUpdateManyArgs} args - Arguments to update one or more rows.
     * @example
     * // Update many Notes
     * const note = await prisma.note.updateMany({
     *   where: {
     *     // ... provide filter here
     *   },
     *   data: {
     *     // ... provide data here
     *   }
     * })
     * 
    **/
    updateMany<T extends NoteUpdateManyArgs<ExtArgs>>(
      args: SelectSubset<T, NoteUpdateManyArgs<ExtArgs>>
    ): Prisma.PrismaPromise<BatchPayload>

    /**
     * Create or update one Note.
     * @param {NoteUpsertArgs} args - Arguments to update or create a Note.
     * @example
     * // Update or create a Note
     * const note = await prisma.note.upsert({
     *   create: {
     *     // ... data to create a Note
     *   },
     *   update: {
     *     // ... in case it already exists, update
     *   },
     *   where: {
     *     // ... the filter for the Note we want to update
     *   }
     * })
    **/
    upsert<T extends NoteUpsertArgs<ExtArgs>>(
      args: SelectSubset<T, NoteUpsertArgs<ExtArgs>>
    ): Prisma__NoteClient<$Types.GetResult<NotePayload<ExtArgs>, T, 'upsert', never>, never, ExtArgs>

    /**
     * Count the number of Notes.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {NoteCountArgs} args - Arguments to filter Notes to count.
     * @example
     * // Count the number of Notes
     * const count = await prisma.note.count({
     *   where: {
     *     // ... the filter for the Notes we want to count
     *   }
     * })
    **/
    count<T extends NoteCountArgs>(
      args?: Subset<T, NoteCountArgs>,
    ): Prisma.PrismaPromise<
      T extends $Utils.Record<'select', any>
        ? T['select'] extends true
          ? number
          : GetScalarType<T['select'], NoteCountAggregateOutputType>
        : number
    >

    /**
     * Allows you to perform aggregations operations on a Note.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {NoteAggregateArgs} args - Select which aggregations you would like to apply and on what fields.
     * @example
     * // Ordered by age ascending
     * // Where email contains prisma.io
     * // Limited to the 10 users
     * const aggregations = await prisma.user.aggregate({
     *   _avg: {
     *     age: true,
     *   },
     *   where: {
     *     email: {
     *       contains: "prisma.io",
     *     },
     *   },
     *   orderBy: {
     *     age: "asc",
     *   },
     *   take: 10,
     * })
    **/
    aggregate<T extends NoteAggregateArgs>(args: Subset<T, NoteAggregateArgs>): Prisma.PrismaPromise<GetNoteAggregateType<T>>

    /**
     * Group by Note.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {NoteGroupByArgs} args - Group by arguments.
     * @example
     * // Group by city, order by createdAt, get count
     * const result = await prisma.user.groupBy({
     *   by: ['city', 'createdAt'],
     *   orderBy: {
     *     createdAt: true
     *   },
     *   _count: {
     *     _all: true
     *   },
     * })
     * 
    **/
    groupBy<
      T extends NoteGroupByArgs,
      HasSelectOrTake extends Or<
        Extends<'skip', Keys<T>>,
        Extends<'take', Keys<T>>
      >,
      OrderByArg extends True extends HasSelectOrTake
        ? { orderBy: NoteGroupByArgs['orderBy'] }
        : { orderBy?: NoteGroupByArgs['orderBy'] },
      OrderFields extends ExcludeUnderscoreKeys<Keys<MaybeTupleToUnion<T['orderBy']>>>,
      ByFields extends TupleToUnion<T['by']>,
      ByValid extends Has<ByFields, OrderFields>,
      HavingFields extends GetHavingFields<T['having']>,
      HavingValid extends Has<ByFields, HavingFields>,
      ByEmpty extends T['by'] extends never[] ? True : False,
      InputErrors extends ByEmpty extends True
      ? `Error: "by" must not be empty.`
      : HavingValid extends False
      ? {
          [P in HavingFields]: P extends ByFields
            ? never
            : P extends string
            ? `Error: Field "${P}" used in "having" needs to be provided in "by".`
            : [
                Error,
                'Field ',
                P,
                ` in "having" needs to be provided in "by"`,
              ]
        }[HavingFields]
      : 'take' extends Keys<T>
      ? 'orderBy' extends Keys<T>
        ? ByValid extends True
          ? {}
          : {
              [P in OrderFields]: P extends ByFields
                ? never
                : `Error: Field "${P}" in "orderBy" needs to be provided in "by"`
            }[OrderFields]
        : 'Error: If you provide "take", you also need to provide "orderBy"'
      : 'skip' extends Keys<T>
      ? 'orderBy' extends Keys<T>
        ? ByValid extends True
          ? {}
          : {
              [P in OrderFields]: P extends ByFields
                ? never
                : `Error: Field "${P}" in "orderBy" needs to be provided in "by"`
            }[OrderFields]
        : 'Error: If you provide "skip", you also need to provide "orderBy"'
      : ByValid extends True
      ? {}
      : {
          [P in OrderFields]: P extends ByFields
            ? never
            : `Error: Field "${P}" in "orderBy" needs to be provided in "by"`
        }[OrderFields]
    >(args: SubsetIntersection<T, NoteGroupByArgs, OrderByArg> & InputErrors): {} extends InputErrors ? GetNoteGroupByPayload<T> : Prisma.PrismaPromise<InputErrors>

  }

  /**
   * The delegate class that acts as a "Promise-like" for Note.
   * Why is this prefixed with `Prisma__`?
   * Because we want to prevent naming conflicts as mentioned in
   * https://github.com/prisma/prisma-client-js/issues/707
   */
  export class Prisma__NoteClient<T, Null = never, ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> implements Prisma.PrismaPromise<T> {
    private readonly _dmmf;
    private readonly _queryType;
    private readonly _rootField;
    private readonly _clientMethod;
    private readonly _args;
    private readonly _dataPath;
    private readonly _errorFormat;
    private readonly _measurePerformance?;
    private _isList;
    private _callsite;
    private _requestPromise?;
    readonly [Symbol.toStringTag]: 'PrismaPromise';
    constructor(_dmmf: runtime.DMMFClass, _queryType: 'query' | 'mutation', _rootField: string, _clientMethod: string, _args: any, _dataPath: string[], _errorFormat: ErrorFormat, _measurePerformance?: boolean | undefined, _isList?: boolean);

    vault<T extends DVaultArgs<ExtArgs> = {}>(args?: Subset<T, DVaultArgs<ExtArgs>>): Prisma__DVaultClient<$Types.GetResult<DVaultPayload<ExtArgs>, T, 'findUnique', never> | Null, never, ExtArgs>;

    private get _document();
    /**
     * Attaches callbacks for the resolution and/or rejection of the Promise.
     * @param onfulfilled The callback to execute when the Promise is resolved.
     * @param onrejected The callback to execute when the Promise is rejected.
     * @returns A Promise for the completion of which ever callback is executed.
     */
    then<TResult1 = T, TResult2 = never>(onfulfilled?: ((value: T) => TResult1 | PromiseLike<TResult1>) | undefined | null, onrejected?: ((reason: any) => TResult2 | PromiseLike<TResult2>) | undefined | null): Promise<TResult1 | TResult2>;
    /**
     * Attaches a callback for only the rejection of the Promise.
     * @param onrejected The callback to execute when the Promise is rejected.
     * @returns A Promise for the completion of the callback.
     */
    catch<TResult = never>(onrejected?: ((reason: any) => TResult | PromiseLike<TResult>) | undefined | null): Promise<T | TResult>;
    /**
     * Attaches a callback that is invoked when the Promise is settled (fulfilled or rejected). The
     * resolved value cannot be modified from the callback.
     * @param onfinally The callback to execute when the Promise is settled (fulfilled or rejected).
     * @returns A Promise for the completion of the callback.
     */
    finally(onfinally?: (() => void) | undefined | null): Promise<T>;
  }



  // Custom InputTypes

  /**
   * Note base type for findUnique actions
   */
  export type NoteFindUniqueArgsBase<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Note
     */
    select?: NoteSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: NoteInclude<ExtArgs> | null
    /**
     * Filter, which Note to fetch.
     */
    where: NoteWhereUniqueInput
  }

  /**
   * Note findUnique
   */
  export interface NoteFindUniqueArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> extends NoteFindUniqueArgsBase<ExtArgs> {
   /**
    * Throw an Error if query returns no results
    * @deprecated since 4.0.0: use `findUniqueOrThrow` method instead
    */
    rejectOnNotFound?: RejectOnNotFound
  }
      

  /**
   * Note findUniqueOrThrow
   */
  export type NoteFindUniqueOrThrowArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Note
     */
    select?: NoteSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: NoteInclude<ExtArgs> | null
    /**
     * Filter, which Note to fetch.
     */
    where: NoteWhereUniqueInput
  }


  /**
   * Note base type for findFirst actions
   */
  export type NoteFindFirstArgsBase<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Note
     */
    select?: NoteSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: NoteInclude<ExtArgs> | null
    /**
     * Filter, which Note to fetch.
     */
    where?: NoteWhereInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/sorting Sorting Docs}
     * 
     * Determine the order of Notes to fetch.
     */
    orderBy?: Enumerable<NoteOrderByWithRelationInput>
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination#cursor-based-pagination Cursor Docs}
     * 
     * Sets the position for searching for Notes.
     */
    cursor?: NoteWhereUniqueInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Take `±n` Notes from the position of the cursor.
     */
    take?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Skip the first `n` Notes.
     */
    skip?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/distinct Distinct Docs}
     * 
     * Filter by unique combinations of Notes.
     */
    distinct?: Enumerable<NoteScalarFieldEnum>
  }

  /**
   * Note findFirst
   */
  export interface NoteFindFirstArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> extends NoteFindFirstArgsBase<ExtArgs> {
   /**
    * Throw an Error if query returns no results
    * @deprecated since 4.0.0: use `findFirstOrThrow` method instead
    */
    rejectOnNotFound?: RejectOnNotFound
  }
      

  /**
   * Note findFirstOrThrow
   */
  export type NoteFindFirstOrThrowArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Note
     */
    select?: NoteSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: NoteInclude<ExtArgs> | null
    /**
     * Filter, which Note to fetch.
     */
    where?: NoteWhereInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/sorting Sorting Docs}
     * 
     * Determine the order of Notes to fetch.
     */
    orderBy?: Enumerable<NoteOrderByWithRelationInput>
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination#cursor-based-pagination Cursor Docs}
     * 
     * Sets the position for searching for Notes.
     */
    cursor?: NoteWhereUniqueInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Take `±n` Notes from the position of the cursor.
     */
    take?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Skip the first `n` Notes.
     */
    skip?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/distinct Distinct Docs}
     * 
     * Filter by unique combinations of Notes.
     */
    distinct?: Enumerable<NoteScalarFieldEnum>
  }


  /**
   * Note findMany
   */
  export type NoteFindManyArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Note
     */
    select?: NoteSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: NoteInclude<ExtArgs> | null
    /**
     * Filter, which Notes to fetch.
     */
    where?: NoteWhereInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/sorting Sorting Docs}
     * 
     * Determine the order of Notes to fetch.
     */
    orderBy?: Enumerable<NoteOrderByWithRelationInput>
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination#cursor-based-pagination Cursor Docs}
     * 
     * Sets the position for listing Notes.
     */
    cursor?: NoteWhereUniqueInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Take `±n` Notes from the position of the cursor.
     */
    take?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Skip the first `n` Notes.
     */
    skip?: number
    distinct?: Enumerable<NoteScalarFieldEnum>
  }


  /**
   * Note create
   */
  export type NoteCreateArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Note
     */
    select?: NoteSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: NoteInclude<ExtArgs> | null
    /**
     * The data needed to create a Note.
     */
    data: XOR<NoteCreateInput, NoteUncheckedCreateInput>
  }


  /**
   * Note update
   */
  export type NoteUpdateArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Note
     */
    select?: NoteSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: NoteInclude<ExtArgs> | null
    /**
     * The data needed to update a Note.
     */
    data: XOR<NoteUpdateInput, NoteUncheckedUpdateInput>
    /**
     * Choose, which Note to update.
     */
    where: NoteWhereUniqueInput
  }


  /**
   * Note updateMany
   */
  export type NoteUpdateManyArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * The data used to update Notes.
     */
    data: XOR<NoteUpdateManyMutationInput, NoteUncheckedUpdateManyInput>
    /**
     * Filter which Notes to update
     */
    where?: NoteWhereInput
  }


  /**
   * Note upsert
   */
  export type NoteUpsertArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Note
     */
    select?: NoteSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: NoteInclude<ExtArgs> | null
    /**
     * The filter to search for the Note to update in case it exists.
     */
    where: NoteWhereUniqueInput
    /**
     * In case the Note found by the `where` argument doesn't exist, create a new Note with this data.
     */
    create: XOR<NoteCreateInput, NoteUncheckedCreateInput>
    /**
     * In case the Note was found with the provided `where` argument, update it with this data.
     */
    update: XOR<NoteUpdateInput, NoteUncheckedUpdateInput>
  }


  /**
   * Note delete
   */
  export type NoteDeleteArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Note
     */
    select?: NoteSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: NoteInclude<ExtArgs> | null
    /**
     * Filter which Note to delete.
     */
    where: NoteWhereUniqueInput
  }


  /**
   * Note deleteMany
   */
  export type NoteDeleteManyArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Filter which Notes to delete
     */
    where?: NoteWhereInput
  }


  /**
   * Note without action
   */
  export type NoteArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Note
     */
    select?: NoteSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: NoteInclude<ExtArgs> | null
  }



  /**
   * Model DVault
   */


  export type AggregateDVault = {
    _count: DVaultCountAggregateOutputType | null
    _avg: DVaultAvgAggregateOutputType | null
    _sum: DVaultSumAggregateOutputType | null
    _min: DVaultMinAggregateOutputType | null
    _max: DVaultMaxAggregateOutputType | null
  }

  export type DVaultAvgAggregateOutputType = {
    id: number | null
  }

  export type DVaultSumAggregateOutputType = {
    id: number | null
  }

  export type DVaultMinAggregateOutputType = {
    id: number | null
    name: string | null
    fsPath: string | null
    wsRoot: string | null
  }

  export type DVaultMaxAggregateOutputType = {
    id: number | null
    name: string | null
    fsPath: string | null
    wsRoot: string | null
  }

  export type DVaultCountAggregateOutputType = {
    id: number
    name: number
    fsPath: number
    wsRoot: number
    _all: number
  }


  export type DVaultAvgAggregateInputType = {
    id?: true
  }

  export type DVaultSumAggregateInputType = {
    id?: true
  }

  export type DVaultMinAggregateInputType = {
    id?: true
    name?: true
    fsPath?: true
    wsRoot?: true
  }

  export type DVaultMaxAggregateInputType = {
    id?: true
    name?: true
    fsPath?: true
    wsRoot?: true
  }

  export type DVaultCountAggregateInputType = {
    id?: true
    name?: true
    fsPath?: true
    wsRoot?: true
    _all?: true
  }

  export type DVaultAggregateArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Filter which DVault to aggregate.
     */
    where?: DVaultWhereInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/sorting Sorting Docs}
     * 
     * Determine the order of DVaults to fetch.
     */
    orderBy?: Enumerable<DVaultOrderByWithRelationInput>
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination#cursor-based-pagination Cursor Docs}
     * 
     * Sets the start position
     */
    cursor?: DVaultWhereUniqueInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Take `±n` DVaults from the position of the cursor.
     */
    take?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Skip the first `n` DVaults.
     */
    skip?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/aggregations Aggregation Docs}
     * 
     * Count returned DVaults
    **/
    _count?: true | DVaultCountAggregateInputType
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/aggregations Aggregation Docs}
     * 
     * Select which fields to average
    **/
    _avg?: DVaultAvgAggregateInputType
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/aggregations Aggregation Docs}
     * 
     * Select which fields to sum
    **/
    _sum?: DVaultSumAggregateInputType
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/aggregations Aggregation Docs}
     * 
     * Select which fields to find the minimum value
    **/
    _min?: DVaultMinAggregateInputType
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/aggregations Aggregation Docs}
     * 
     * Select which fields to find the maximum value
    **/
    _max?: DVaultMaxAggregateInputType
  }

  export type GetDVaultAggregateType<T extends DVaultAggregateArgs> = {
        [P in keyof T & keyof AggregateDVault]: P extends '_count' | 'count'
      ? T[P] extends true
        ? number
        : GetScalarType<T[P], AggregateDVault[P]>
      : GetScalarType<T[P], AggregateDVault[P]>
  }




  export type DVaultGroupByArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    where?: DVaultWhereInput
    orderBy?: Enumerable<DVaultOrderByWithAggregationInput>
    by: DVaultScalarFieldEnum[]
    having?: DVaultScalarWhereWithAggregatesInput
    take?: number
    skip?: number
    _count?: DVaultCountAggregateInputType | true
    _avg?: DVaultAvgAggregateInputType
    _sum?: DVaultSumAggregateInputType
    _min?: DVaultMinAggregateInputType
    _max?: DVaultMaxAggregateInputType
  }


  export type DVaultGroupByOutputType = {
    id: number
    name: string | null
    fsPath: string
    wsRoot: string
    _count: DVaultCountAggregateOutputType | null
    _avg: DVaultAvgAggregateOutputType | null
    _sum: DVaultSumAggregateOutputType | null
    _min: DVaultMinAggregateOutputType | null
    _max: DVaultMaxAggregateOutputType | null
  }

  type GetDVaultGroupByPayload<T extends DVaultGroupByArgs> = Prisma.PrismaPromise<
    Array<
      PickArray<DVaultGroupByOutputType, T['by']> &
        {
          [P in ((keyof T) & (keyof DVaultGroupByOutputType))]: P extends '_count'
            ? T[P] extends boolean
              ? number
              : GetScalarType<T[P], DVaultGroupByOutputType[P]>
            : GetScalarType<T[P], DVaultGroupByOutputType[P]>
        }
      >
    >


  export type DVaultSelect<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = $Extensions.GetSelect<{
    id?: boolean
    name?: boolean
    fsPath?: boolean
    wsRoot?: boolean
    workspace?: boolean | WorkspaceArgs<ExtArgs>
    Note?: boolean | DVault$NoteArgs<ExtArgs>
    _count?: boolean | DVaultCountOutputTypeArgs<ExtArgs>
  }, ExtArgs["result"]["dVault"]>

  export type DVaultSelectScalar = {
    id?: boolean
    name?: boolean
    fsPath?: boolean
    wsRoot?: boolean
  }

  export type DVaultInclude<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    workspace?: boolean | WorkspaceArgs<ExtArgs>
    Note?: boolean | DVault$NoteArgs<ExtArgs>
    _count?: boolean | DVaultCountOutputTypeArgs<ExtArgs>
  }


  type DVaultGetPayload<S extends boolean | null | undefined | DVaultArgs> = $Types.GetResult<DVaultPayload, S>

  type DVaultCountArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = 
    Omit<DVaultFindManyArgs, 'select' | 'include'> & {
      select?: DVaultCountAggregateInputType | true
    }

  export interface DVaultDelegate<GlobalRejectSettings extends Prisma.RejectOnNotFound | Prisma.RejectPerOperation | false | undefined, ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> {
    [K: symbol]: { types: Prisma.TypeMap<ExtArgs>['model']['DVault'], meta: { name: 'DVault' } }
    /**
     * Find zero or one DVault that matches the filter.
     * @param {DVaultFindUniqueArgs} args - Arguments to find a DVault
     * @example
     * // Get one DVault
     * const dVault = await prisma.dVault.findUnique({
     *   where: {
     *     // ... provide filter here
     *   }
     * })
    **/
    findUnique<T extends DVaultFindUniqueArgs<ExtArgs>, LocalRejectSettings = T["rejectOnNotFound"] extends RejectOnNotFound ? T['rejectOnNotFound'] : undefined>(
      args: SelectSubset<T, DVaultFindUniqueArgs<ExtArgs>>
    ): HasReject<GlobalRejectSettings, LocalRejectSettings, 'findUnique', 'DVault'> extends True ? Prisma__DVaultClient<$Types.GetResult<DVaultPayload<ExtArgs>, T, 'findUnique', never>, never, ExtArgs> : Prisma__DVaultClient<$Types.GetResult<DVaultPayload<ExtArgs>, T, 'findUnique', never> | null, null, ExtArgs>

    /**
     * Find one DVault that matches the filter or throw an error  with `error.code='P2025'` 
     *     if no matches were found.
     * @param {DVaultFindUniqueOrThrowArgs} args - Arguments to find a DVault
     * @example
     * // Get one DVault
     * const dVault = await prisma.dVault.findUniqueOrThrow({
     *   where: {
     *     // ... provide filter here
     *   }
     * })
    **/
    findUniqueOrThrow<T extends DVaultFindUniqueOrThrowArgs<ExtArgs>>(
      args?: SelectSubset<T, DVaultFindUniqueOrThrowArgs<ExtArgs>>
    ): Prisma__DVaultClient<$Types.GetResult<DVaultPayload<ExtArgs>, T, 'findUniqueOrThrow', never>, never, ExtArgs>

    /**
     * Find the first DVault that matches the filter.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {DVaultFindFirstArgs} args - Arguments to find a DVault
     * @example
     * // Get one DVault
     * const dVault = await prisma.dVault.findFirst({
     *   where: {
     *     // ... provide filter here
     *   }
     * })
    **/
    findFirst<T extends DVaultFindFirstArgs<ExtArgs>, LocalRejectSettings = T["rejectOnNotFound"] extends RejectOnNotFound ? T['rejectOnNotFound'] : undefined>(
      args?: SelectSubset<T, DVaultFindFirstArgs<ExtArgs>>
    ): HasReject<GlobalRejectSettings, LocalRejectSettings, 'findFirst', 'DVault'> extends True ? Prisma__DVaultClient<$Types.GetResult<DVaultPayload<ExtArgs>, T, 'findFirst', never>, never, ExtArgs> : Prisma__DVaultClient<$Types.GetResult<DVaultPayload<ExtArgs>, T, 'findFirst', never> | null, null, ExtArgs>

    /**
     * Find the first DVault that matches the filter or
     * throw `NotFoundError` if no matches were found.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {DVaultFindFirstOrThrowArgs} args - Arguments to find a DVault
     * @example
     * // Get one DVault
     * const dVault = await prisma.dVault.findFirstOrThrow({
     *   where: {
     *     // ... provide filter here
     *   }
     * })
    **/
    findFirstOrThrow<T extends DVaultFindFirstOrThrowArgs<ExtArgs>>(
      args?: SelectSubset<T, DVaultFindFirstOrThrowArgs<ExtArgs>>
    ): Prisma__DVaultClient<$Types.GetResult<DVaultPayload<ExtArgs>, T, 'findFirstOrThrow', never>, never, ExtArgs>

    /**
     * Find zero or more DVaults that matches the filter.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {DVaultFindManyArgs=} args - Arguments to filter and select certain fields only.
     * @example
     * // Get all DVaults
     * const dVaults = await prisma.dVault.findMany()
     * 
     * // Get first 10 DVaults
     * const dVaults = await prisma.dVault.findMany({ take: 10 })
     * 
     * // Only select the `id`
     * const dVaultWithIdOnly = await prisma.dVault.findMany({ select: { id: true } })
     * 
    **/
    findMany<T extends DVaultFindManyArgs<ExtArgs>>(
      args?: SelectSubset<T, DVaultFindManyArgs<ExtArgs>>
    ): Prisma.PrismaPromise<$Types.GetResult<DVaultPayload<ExtArgs>, T, 'findMany', never>>

    /**
     * Create a DVault.
     * @param {DVaultCreateArgs} args - Arguments to create a DVault.
     * @example
     * // Create one DVault
     * const DVault = await prisma.dVault.create({
     *   data: {
     *     // ... data to create a DVault
     *   }
     * })
     * 
    **/
    create<T extends DVaultCreateArgs<ExtArgs>>(
      args: SelectSubset<T, DVaultCreateArgs<ExtArgs>>
    ): Prisma__DVaultClient<$Types.GetResult<DVaultPayload<ExtArgs>, T, 'create', never>, never, ExtArgs>

    /**
     * Delete a DVault.
     * @param {DVaultDeleteArgs} args - Arguments to delete one DVault.
     * @example
     * // Delete one DVault
     * const DVault = await prisma.dVault.delete({
     *   where: {
     *     // ... filter to delete one DVault
     *   }
     * })
     * 
    **/
    delete<T extends DVaultDeleteArgs<ExtArgs>>(
      args: SelectSubset<T, DVaultDeleteArgs<ExtArgs>>
    ): Prisma__DVaultClient<$Types.GetResult<DVaultPayload<ExtArgs>, T, 'delete', never>, never, ExtArgs>

    /**
     * Update one DVault.
     * @param {DVaultUpdateArgs} args - Arguments to update one DVault.
     * @example
     * // Update one DVault
     * const dVault = await prisma.dVault.update({
     *   where: {
     *     // ... provide filter here
     *   },
     *   data: {
     *     // ... provide data here
     *   }
     * })
     * 
    **/
    update<T extends DVaultUpdateArgs<ExtArgs>>(
      args: SelectSubset<T, DVaultUpdateArgs<ExtArgs>>
    ): Prisma__DVaultClient<$Types.GetResult<DVaultPayload<ExtArgs>, T, 'update', never>, never, ExtArgs>

    /**
     * Delete zero or more DVaults.
     * @param {DVaultDeleteManyArgs} args - Arguments to filter DVaults to delete.
     * @example
     * // Delete a few DVaults
     * const { count } = await prisma.dVault.deleteMany({
     *   where: {
     *     // ... provide filter here
     *   }
     * })
     * 
    **/
    deleteMany<T extends DVaultDeleteManyArgs<ExtArgs>>(
      args?: SelectSubset<T, DVaultDeleteManyArgs<ExtArgs>>
    ): Prisma.PrismaPromise<BatchPayload>

    /**
     * Update zero or more DVaults.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {DVaultUpdateManyArgs} args - Arguments to update one or more rows.
     * @example
     * // Update many DVaults
     * const dVault = await prisma.dVault.updateMany({
     *   where: {
     *     // ... provide filter here
     *   },
     *   data: {
     *     // ... provide data here
     *   }
     * })
     * 
    **/
    updateMany<T extends DVaultUpdateManyArgs<ExtArgs>>(
      args: SelectSubset<T, DVaultUpdateManyArgs<ExtArgs>>
    ): Prisma.PrismaPromise<BatchPayload>

    /**
     * Create or update one DVault.
     * @param {DVaultUpsertArgs} args - Arguments to update or create a DVault.
     * @example
     * // Update or create a DVault
     * const dVault = await prisma.dVault.upsert({
     *   create: {
     *     // ... data to create a DVault
     *   },
     *   update: {
     *     // ... in case it already exists, update
     *   },
     *   where: {
     *     // ... the filter for the DVault we want to update
     *   }
     * })
    **/
    upsert<T extends DVaultUpsertArgs<ExtArgs>>(
      args: SelectSubset<T, DVaultUpsertArgs<ExtArgs>>
    ): Prisma__DVaultClient<$Types.GetResult<DVaultPayload<ExtArgs>, T, 'upsert', never>, never, ExtArgs>

    /**
     * Count the number of DVaults.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {DVaultCountArgs} args - Arguments to filter DVaults to count.
     * @example
     * // Count the number of DVaults
     * const count = await prisma.dVault.count({
     *   where: {
     *     // ... the filter for the DVaults we want to count
     *   }
     * })
    **/
    count<T extends DVaultCountArgs>(
      args?: Subset<T, DVaultCountArgs>,
    ): Prisma.PrismaPromise<
      T extends $Utils.Record<'select', any>
        ? T['select'] extends true
          ? number
          : GetScalarType<T['select'], DVaultCountAggregateOutputType>
        : number
    >

    /**
     * Allows you to perform aggregations operations on a DVault.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {DVaultAggregateArgs} args - Select which aggregations you would like to apply and on what fields.
     * @example
     * // Ordered by age ascending
     * // Where email contains prisma.io
     * // Limited to the 10 users
     * const aggregations = await prisma.user.aggregate({
     *   _avg: {
     *     age: true,
     *   },
     *   where: {
     *     email: {
     *       contains: "prisma.io",
     *     },
     *   },
     *   orderBy: {
     *     age: "asc",
     *   },
     *   take: 10,
     * })
    **/
    aggregate<T extends DVaultAggregateArgs>(args: Subset<T, DVaultAggregateArgs>): Prisma.PrismaPromise<GetDVaultAggregateType<T>>

    /**
     * Group by DVault.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {DVaultGroupByArgs} args - Group by arguments.
     * @example
     * // Group by city, order by createdAt, get count
     * const result = await prisma.user.groupBy({
     *   by: ['city', 'createdAt'],
     *   orderBy: {
     *     createdAt: true
     *   },
     *   _count: {
     *     _all: true
     *   },
     * })
     * 
    **/
    groupBy<
      T extends DVaultGroupByArgs,
      HasSelectOrTake extends Or<
        Extends<'skip', Keys<T>>,
        Extends<'take', Keys<T>>
      >,
      OrderByArg extends True extends HasSelectOrTake
        ? { orderBy: DVaultGroupByArgs['orderBy'] }
        : { orderBy?: DVaultGroupByArgs['orderBy'] },
      OrderFields extends ExcludeUnderscoreKeys<Keys<MaybeTupleToUnion<T['orderBy']>>>,
      ByFields extends TupleToUnion<T['by']>,
      ByValid extends Has<ByFields, OrderFields>,
      HavingFields extends GetHavingFields<T['having']>,
      HavingValid extends Has<ByFields, HavingFields>,
      ByEmpty extends T['by'] extends never[] ? True : False,
      InputErrors extends ByEmpty extends True
      ? `Error: "by" must not be empty.`
      : HavingValid extends False
      ? {
          [P in HavingFields]: P extends ByFields
            ? never
            : P extends string
            ? `Error: Field "${P}" used in "having" needs to be provided in "by".`
            : [
                Error,
                'Field ',
                P,
                ` in "having" needs to be provided in "by"`,
              ]
        }[HavingFields]
      : 'take' extends Keys<T>
      ? 'orderBy' extends Keys<T>
        ? ByValid extends True
          ? {}
          : {
              [P in OrderFields]: P extends ByFields
                ? never
                : `Error: Field "${P}" in "orderBy" needs to be provided in "by"`
            }[OrderFields]
        : 'Error: If you provide "take", you also need to provide "orderBy"'
      : 'skip' extends Keys<T>
      ? 'orderBy' extends Keys<T>
        ? ByValid extends True
          ? {}
          : {
              [P in OrderFields]: P extends ByFields
                ? never
                : `Error: Field "${P}" in "orderBy" needs to be provided in "by"`
            }[OrderFields]
        : 'Error: If you provide "skip", you also need to provide "orderBy"'
      : ByValid extends True
      ? {}
      : {
          [P in OrderFields]: P extends ByFields
            ? never
            : `Error: Field "${P}" in "orderBy" needs to be provided in "by"`
        }[OrderFields]
    >(args: SubsetIntersection<T, DVaultGroupByArgs, OrderByArg> & InputErrors): {} extends InputErrors ? GetDVaultGroupByPayload<T> : Prisma.PrismaPromise<InputErrors>

  }

  /**
   * The delegate class that acts as a "Promise-like" for DVault.
   * Why is this prefixed with `Prisma__`?
   * Because we want to prevent naming conflicts as mentioned in
   * https://github.com/prisma/prisma-client-js/issues/707
   */
  export class Prisma__DVaultClient<T, Null = never, ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> implements Prisma.PrismaPromise<T> {
    private readonly _dmmf;
    private readonly _queryType;
    private readonly _rootField;
    private readonly _clientMethod;
    private readonly _args;
    private readonly _dataPath;
    private readonly _errorFormat;
    private readonly _measurePerformance?;
    private _isList;
    private _callsite;
    private _requestPromise?;
    readonly [Symbol.toStringTag]: 'PrismaPromise';
    constructor(_dmmf: runtime.DMMFClass, _queryType: 'query' | 'mutation', _rootField: string, _clientMethod: string, _args: any, _dataPath: string[], _errorFormat: ErrorFormat, _measurePerformance?: boolean | undefined, _isList?: boolean);

    workspace<T extends WorkspaceArgs<ExtArgs> = {}>(args?: Subset<T, WorkspaceArgs<ExtArgs>>): Prisma__WorkspaceClient<$Types.GetResult<WorkspacePayload<ExtArgs>, T, 'findUnique', never> | Null, never, ExtArgs>;

    Note<T extends DVault$NoteArgs<ExtArgs> = {}>(args?: Subset<T, DVault$NoteArgs<ExtArgs>>): Prisma.PrismaPromise<$Types.GetResult<NotePayload<ExtArgs>, T, 'findMany', never>| Null>;

    private get _document();
    /**
     * Attaches callbacks for the resolution and/or rejection of the Promise.
     * @param onfulfilled The callback to execute when the Promise is resolved.
     * @param onrejected The callback to execute when the Promise is rejected.
     * @returns A Promise for the completion of which ever callback is executed.
     */
    then<TResult1 = T, TResult2 = never>(onfulfilled?: ((value: T) => TResult1 | PromiseLike<TResult1>) | undefined | null, onrejected?: ((reason: any) => TResult2 | PromiseLike<TResult2>) | undefined | null): Promise<TResult1 | TResult2>;
    /**
     * Attaches a callback for only the rejection of the Promise.
     * @param onrejected The callback to execute when the Promise is rejected.
     * @returns A Promise for the completion of the callback.
     */
    catch<TResult = never>(onrejected?: ((reason: any) => TResult | PromiseLike<TResult>) | undefined | null): Promise<T | TResult>;
    /**
     * Attaches a callback that is invoked when the Promise is settled (fulfilled or rejected). The
     * resolved value cannot be modified from the callback.
     * @param onfinally The callback to execute when the Promise is settled (fulfilled or rejected).
     * @returns A Promise for the completion of the callback.
     */
    finally(onfinally?: (() => void) | undefined | null): Promise<T>;
  }



  // Custom InputTypes

  /**
   * DVault base type for findUnique actions
   */
  export type DVaultFindUniqueArgsBase<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the DVault
     */
    select?: DVaultSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: DVaultInclude<ExtArgs> | null
    /**
     * Filter, which DVault to fetch.
     */
    where: DVaultWhereUniqueInput
  }

  /**
   * DVault findUnique
   */
  export interface DVaultFindUniqueArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> extends DVaultFindUniqueArgsBase<ExtArgs> {
   /**
    * Throw an Error if query returns no results
    * @deprecated since 4.0.0: use `findUniqueOrThrow` method instead
    */
    rejectOnNotFound?: RejectOnNotFound
  }
      

  /**
   * DVault findUniqueOrThrow
   */
  export type DVaultFindUniqueOrThrowArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the DVault
     */
    select?: DVaultSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: DVaultInclude<ExtArgs> | null
    /**
     * Filter, which DVault to fetch.
     */
    where: DVaultWhereUniqueInput
  }


  /**
   * DVault base type for findFirst actions
   */
  export type DVaultFindFirstArgsBase<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the DVault
     */
    select?: DVaultSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: DVaultInclude<ExtArgs> | null
    /**
     * Filter, which DVault to fetch.
     */
    where?: DVaultWhereInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/sorting Sorting Docs}
     * 
     * Determine the order of DVaults to fetch.
     */
    orderBy?: Enumerable<DVaultOrderByWithRelationInput>
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination#cursor-based-pagination Cursor Docs}
     * 
     * Sets the position for searching for DVaults.
     */
    cursor?: DVaultWhereUniqueInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Take `±n` DVaults from the position of the cursor.
     */
    take?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Skip the first `n` DVaults.
     */
    skip?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/distinct Distinct Docs}
     * 
     * Filter by unique combinations of DVaults.
     */
    distinct?: Enumerable<DVaultScalarFieldEnum>
  }

  /**
   * DVault findFirst
   */
  export interface DVaultFindFirstArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> extends DVaultFindFirstArgsBase<ExtArgs> {
   /**
    * Throw an Error if query returns no results
    * @deprecated since 4.0.0: use `findFirstOrThrow` method instead
    */
    rejectOnNotFound?: RejectOnNotFound
  }
      

  /**
   * DVault findFirstOrThrow
   */
  export type DVaultFindFirstOrThrowArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the DVault
     */
    select?: DVaultSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: DVaultInclude<ExtArgs> | null
    /**
     * Filter, which DVault to fetch.
     */
    where?: DVaultWhereInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/sorting Sorting Docs}
     * 
     * Determine the order of DVaults to fetch.
     */
    orderBy?: Enumerable<DVaultOrderByWithRelationInput>
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination#cursor-based-pagination Cursor Docs}
     * 
     * Sets the position for searching for DVaults.
     */
    cursor?: DVaultWhereUniqueInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Take `±n` DVaults from the position of the cursor.
     */
    take?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Skip the first `n` DVaults.
     */
    skip?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/distinct Distinct Docs}
     * 
     * Filter by unique combinations of DVaults.
     */
    distinct?: Enumerable<DVaultScalarFieldEnum>
  }


  /**
   * DVault findMany
   */
  export type DVaultFindManyArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the DVault
     */
    select?: DVaultSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: DVaultInclude<ExtArgs> | null
    /**
     * Filter, which DVaults to fetch.
     */
    where?: DVaultWhereInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/sorting Sorting Docs}
     * 
     * Determine the order of DVaults to fetch.
     */
    orderBy?: Enumerable<DVaultOrderByWithRelationInput>
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination#cursor-based-pagination Cursor Docs}
     * 
     * Sets the position for listing DVaults.
     */
    cursor?: DVaultWhereUniqueInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Take `±n` DVaults from the position of the cursor.
     */
    take?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Skip the first `n` DVaults.
     */
    skip?: number
    distinct?: Enumerable<DVaultScalarFieldEnum>
  }


  /**
   * DVault create
   */
  export type DVaultCreateArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the DVault
     */
    select?: DVaultSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: DVaultInclude<ExtArgs> | null
    /**
     * The data needed to create a DVault.
     */
    data: XOR<DVaultCreateInput, DVaultUncheckedCreateInput>
  }


  /**
   * DVault update
   */
  export type DVaultUpdateArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the DVault
     */
    select?: DVaultSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: DVaultInclude<ExtArgs> | null
    /**
     * The data needed to update a DVault.
     */
    data: XOR<DVaultUpdateInput, DVaultUncheckedUpdateInput>
    /**
     * Choose, which DVault to update.
     */
    where: DVaultWhereUniqueInput
  }


  /**
   * DVault updateMany
   */
  export type DVaultUpdateManyArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * The data used to update DVaults.
     */
    data: XOR<DVaultUpdateManyMutationInput, DVaultUncheckedUpdateManyInput>
    /**
     * Filter which DVaults to update
     */
    where?: DVaultWhereInput
  }


  /**
   * DVault upsert
   */
  export type DVaultUpsertArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the DVault
     */
    select?: DVaultSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: DVaultInclude<ExtArgs> | null
    /**
     * The filter to search for the DVault to update in case it exists.
     */
    where: DVaultWhereUniqueInput
    /**
     * In case the DVault found by the `where` argument doesn't exist, create a new DVault with this data.
     */
    create: XOR<DVaultCreateInput, DVaultUncheckedCreateInput>
    /**
     * In case the DVault was found with the provided `where` argument, update it with this data.
     */
    update: XOR<DVaultUpdateInput, DVaultUncheckedUpdateInput>
  }


  /**
   * DVault delete
   */
  export type DVaultDeleteArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the DVault
     */
    select?: DVaultSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: DVaultInclude<ExtArgs> | null
    /**
     * Filter which DVault to delete.
     */
    where: DVaultWhereUniqueInput
  }


  /**
   * DVault deleteMany
   */
  export type DVaultDeleteManyArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Filter which DVaults to delete
     */
    where?: DVaultWhereInput
  }


  /**
   * DVault.Note
   */
  export type DVault$NoteArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Note
     */
    select?: NoteSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: NoteInclude<ExtArgs> | null
    where?: NoteWhereInput
    orderBy?: Enumerable<NoteOrderByWithRelationInput>
    cursor?: NoteWhereUniqueInput
    take?: number
    skip?: number
    distinct?: Enumerable<NoteScalarFieldEnum>
  }


  /**
   * DVault without action
   */
  export type DVaultArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the DVault
     */
    select?: DVaultSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: DVaultInclude<ExtArgs> | null
  }



  /**
   * Model Workspace
   */


  export type AggregateWorkspace = {
    _count: WorkspaceCountAggregateOutputType | null
    _avg: WorkspaceAvgAggregateOutputType | null
    _sum: WorkspaceSumAggregateOutputType | null
    _min: WorkspaceMinAggregateOutputType | null
    _max: WorkspaceMaxAggregateOutputType | null
  }

  export type WorkspaceAvgAggregateOutputType = {
    prismaSchemaVersion: number | null
  }

  export type WorkspaceSumAggregateOutputType = {
    prismaSchemaVersion: number | null
  }

  export type WorkspaceMinAggregateOutputType = {
    wsRoot: string | null
    prismaSchemaVersion: number | null
  }

  export type WorkspaceMaxAggregateOutputType = {
    wsRoot: string | null
    prismaSchemaVersion: number | null
  }

  export type WorkspaceCountAggregateOutputType = {
    wsRoot: number
    prismaSchemaVersion: number
    _all: number
  }


  export type WorkspaceAvgAggregateInputType = {
    prismaSchemaVersion?: true
  }

  export type WorkspaceSumAggregateInputType = {
    prismaSchemaVersion?: true
  }

  export type WorkspaceMinAggregateInputType = {
    wsRoot?: true
    prismaSchemaVersion?: true
  }

  export type WorkspaceMaxAggregateInputType = {
    wsRoot?: true
    prismaSchemaVersion?: true
  }

  export type WorkspaceCountAggregateInputType = {
    wsRoot?: true
    prismaSchemaVersion?: true
    _all?: true
  }

  export type WorkspaceAggregateArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Filter which Workspace to aggregate.
     */
    where?: WorkspaceWhereInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/sorting Sorting Docs}
     * 
     * Determine the order of Workspaces to fetch.
     */
    orderBy?: Enumerable<WorkspaceOrderByWithRelationInput>
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination#cursor-based-pagination Cursor Docs}
     * 
     * Sets the start position
     */
    cursor?: WorkspaceWhereUniqueInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Take `±n` Workspaces from the position of the cursor.
     */
    take?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Skip the first `n` Workspaces.
     */
    skip?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/aggregations Aggregation Docs}
     * 
     * Count returned Workspaces
    **/
    _count?: true | WorkspaceCountAggregateInputType
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/aggregations Aggregation Docs}
     * 
     * Select which fields to average
    **/
    _avg?: WorkspaceAvgAggregateInputType
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/aggregations Aggregation Docs}
     * 
     * Select which fields to sum
    **/
    _sum?: WorkspaceSumAggregateInputType
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/aggregations Aggregation Docs}
     * 
     * Select which fields to find the minimum value
    **/
    _min?: WorkspaceMinAggregateInputType
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/aggregations Aggregation Docs}
     * 
     * Select which fields to find the maximum value
    **/
    _max?: WorkspaceMaxAggregateInputType
  }

  export type GetWorkspaceAggregateType<T extends WorkspaceAggregateArgs> = {
        [P in keyof T & keyof AggregateWorkspace]: P extends '_count' | 'count'
      ? T[P] extends true
        ? number
        : GetScalarType<T[P], AggregateWorkspace[P]>
      : GetScalarType<T[P], AggregateWorkspace[P]>
  }




  export type WorkspaceGroupByArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    where?: WorkspaceWhereInput
    orderBy?: Enumerable<WorkspaceOrderByWithAggregationInput>
    by: WorkspaceScalarFieldEnum[]
    having?: WorkspaceScalarWhereWithAggregatesInput
    take?: number
    skip?: number
    _count?: WorkspaceCountAggregateInputType | true
    _avg?: WorkspaceAvgAggregateInputType
    _sum?: WorkspaceSumAggregateInputType
    _min?: WorkspaceMinAggregateInputType
    _max?: WorkspaceMaxAggregateInputType
  }


  export type WorkspaceGroupByOutputType = {
    wsRoot: string
    prismaSchemaVersion: number
    _count: WorkspaceCountAggregateOutputType | null
    _avg: WorkspaceAvgAggregateOutputType | null
    _sum: WorkspaceSumAggregateOutputType | null
    _min: WorkspaceMinAggregateOutputType | null
    _max: WorkspaceMaxAggregateOutputType | null
  }

  type GetWorkspaceGroupByPayload<T extends WorkspaceGroupByArgs> = Prisma.PrismaPromise<
    Array<
      PickArray<WorkspaceGroupByOutputType, T['by']> &
        {
          [P in ((keyof T) & (keyof WorkspaceGroupByOutputType))]: P extends '_count'
            ? T[P] extends boolean
              ? number
              : GetScalarType<T[P], WorkspaceGroupByOutputType[P]>
            : GetScalarType<T[P], WorkspaceGroupByOutputType[P]>
        }
      >
    >


  export type WorkspaceSelect<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = $Extensions.GetSelect<{
    wsRoot?: boolean
    prismaSchemaVersion?: boolean
    vaults?: boolean | Workspace$vaultsArgs<ExtArgs>
    _count?: boolean | WorkspaceCountOutputTypeArgs<ExtArgs>
  }, ExtArgs["result"]["workspace"]>

  export type WorkspaceSelectScalar = {
    wsRoot?: boolean
    prismaSchemaVersion?: boolean
  }

  export type WorkspaceInclude<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    vaults?: boolean | Workspace$vaultsArgs<ExtArgs>
    _count?: boolean | WorkspaceCountOutputTypeArgs<ExtArgs>
  }


  type WorkspaceGetPayload<S extends boolean | null | undefined | WorkspaceArgs> = $Types.GetResult<WorkspacePayload, S>

  type WorkspaceCountArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = 
    Omit<WorkspaceFindManyArgs, 'select' | 'include'> & {
      select?: WorkspaceCountAggregateInputType | true
    }

  export interface WorkspaceDelegate<GlobalRejectSettings extends Prisma.RejectOnNotFound | Prisma.RejectPerOperation | false | undefined, ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> {
    [K: symbol]: { types: Prisma.TypeMap<ExtArgs>['model']['Workspace'], meta: { name: 'Workspace' } }
    /**
     * Find zero or one Workspace that matches the filter.
     * @param {WorkspaceFindUniqueArgs} args - Arguments to find a Workspace
     * @example
     * // Get one Workspace
     * const workspace = await prisma.workspace.findUnique({
     *   where: {
     *     // ... provide filter here
     *   }
     * })
    **/
    findUnique<T extends WorkspaceFindUniqueArgs<ExtArgs>, LocalRejectSettings = T["rejectOnNotFound"] extends RejectOnNotFound ? T['rejectOnNotFound'] : undefined>(
      args: SelectSubset<T, WorkspaceFindUniqueArgs<ExtArgs>>
    ): HasReject<GlobalRejectSettings, LocalRejectSettings, 'findUnique', 'Workspace'> extends True ? Prisma__WorkspaceClient<$Types.GetResult<WorkspacePayload<ExtArgs>, T, 'findUnique', never>, never, ExtArgs> : Prisma__WorkspaceClient<$Types.GetResult<WorkspacePayload<ExtArgs>, T, 'findUnique', never> | null, null, ExtArgs>

    /**
     * Find one Workspace that matches the filter or throw an error  with `error.code='P2025'` 
     *     if no matches were found.
     * @param {WorkspaceFindUniqueOrThrowArgs} args - Arguments to find a Workspace
     * @example
     * // Get one Workspace
     * const workspace = await prisma.workspace.findUniqueOrThrow({
     *   where: {
     *     // ... provide filter here
     *   }
     * })
    **/
    findUniqueOrThrow<T extends WorkspaceFindUniqueOrThrowArgs<ExtArgs>>(
      args?: SelectSubset<T, WorkspaceFindUniqueOrThrowArgs<ExtArgs>>
    ): Prisma__WorkspaceClient<$Types.GetResult<WorkspacePayload<ExtArgs>, T, 'findUniqueOrThrow', never>, never, ExtArgs>

    /**
     * Find the first Workspace that matches the filter.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {WorkspaceFindFirstArgs} args - Arguments to find a Workspace
     * @example
     * // Get one Workspace
     * const workspace = await prisma.workspace.findFirst({
     *   where: {
     *     // ... provide filter here
     *   }
     * })
    **/
    findFirst<T extends WorkspaceFindFirstArgs<ExtArgs>, LocalRejectSettings = T["rejectOnNotFound"] extends RejectOnNotFound ? T['rejectOnNotFound'] : undefined>(
      args?: SelectSubset<T, WorkspaceFindFirstArgs<ExtArgs>>
    ): HasReject<GlobalRejectSettings, LocalRejectSettings, 'findFirst', 'Workspace'> extends True ? Prisma__WorkspaceClient<$Types.GetResult<WorkspacePayload<ExtArgs>, T, 'findFirst', never>, never, ExtArgs> : Prisma__WorkspaceClient<$Types.GetResult<WorkspacePayload<ExtArgs>, T, 'findFirst', never> | null, null, ExtArgs>

    /**
     * Find the first Workspace that matches the filter or
     * throw `NotFoundError` if no matches were found.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {WorkspaceFindFirstOrThrowArgs} args - Arguments to find a Workspace
     * @example
     * // Get one Workspace
     * const workspace = await prisma.workspace.findFirstOrThrow({
     *   where: {
     *     // ... provide filter here
     *   }
     * })
    **/
    findFirstOrThrow<T extends WorkspaceFindFirstOrThrowArgs<ExtArgs>>(
      args?: SelectSubset<T, WorkspaceFindFirstOrThrowArgs<ExtArgs>>
    ): Prisma__WorkspaceClient<$Types.GetResult<WorkspacePayload<ExtArgs>, T, 'findFirstOrThrow', never>, never, ExtArgs>

    /**
     * Find zero or more Workspaces that matches the filter.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {WorkspaceFindManyArgs=} args - Arguments to filter and select certain fields only.
     * @example
     * // Get all Workspaces
     * const workspaces = await prisma.workspace.findMany()
     * 
     * // Get first 10 Workspaces
     * const workspaces = await prisma.workspace.findMany({ take: 10 })
     * 
     * // Only select the `wsRoot`
     * const workspaceWithWsRootOnly = await prisma.workspace.findMany({ select: { wsRoot: true } })
     * 
    **/
    findMany<T extends WorkspaceFindManyArgs<ExtArgs>>(
      args?: SelectSubset<T, WorkspaceFindManyArgs<ExtArgs>>
    ): Prisma.PrismaPromise<$Types.GetResult<WorkspacePayload<ExtArgs>, T, 'findMany', never>>

    /**
     * Create a Workspace.
     * @param {WorkspaceCreateArgs} args - Arguments to create a Workspace.
     * @example
     * // Create one Workspace
     * const Workspace = await prisma.workspace.create({
     *   data: {
     *     // ... data to create a Workspace
     *   }
     * })
     * 
    **/
    create<T extends WorkspaceCreateArgs<ExtArgs>>(
      args: SelectSubset<T, WorkspaceCreateArgs<ExtArgs>>
    ): Prisma__WorkspaceClient<$Types.GetResult<WorkspacePayload<ExtArgs>, T, 'create', never>, never, ExtArgs>

    /**
     * Delete a Workspace.
     * @param {WorkspaceDeleteArgs} args - Arguments to delete one Workspace.
     * @example
     * // Delete one Workspace
     * const Workspace = await prisma.workspace.delete({
     *   where: {
     *     // ... filter to delete one Workspace
     *   }
     * })
     * 
    **/
    delete<T extends WorkspaceDeleteArgs<ExtArgs>>(
      args: SelectSubset<T, WorkspaceDeleteArgs<ExtArgs>>
    ): Prisma__WorkspaceClient<$Types.GetResult<WorkspacePayload<ExtArgs>, T, 'delete', never>, never, ExtArgs>

    /**
     * Update one Workspace.
     * @param {WorkspaceUpdateArgs} args - Arguments to update one Workspace.
     * @example
     * // Update one Workspace
     * const workspace = await prisma.workspace.update({
     *   where: {
     *     // ... provide filter here
     *   },
     *   data: {
     *     // ... provide data here
     *   }
     * })
     * 
    **/
    update<T extends WorkspaceUpdateArgs<ExtArgs>>(
      args: SelectSubset<T, WorkspaceUpdateArgs<ExtArgs>>
    ): Prisma__WorkspaceClient<$Types.GetResult<WorkspacePayload<ExtArgs>, T, 'update', never>, never, ExtArgs>

    /**
     * Delete zero or more Workspaces.
     * @param {WorkspaceDeleteManyArgs} args - Arguments to filter Workspaces to delete.
     * @example
     * // Delete a few Workspaces
     * const { count } = await prisma.workspace.deleteMany({
     *   where: {
     *     // ... provide filter here
     *   }
     * })
     * 
    **/
    deleteMany<T extends WorkspaceDeleteManyArgs<ExtArgs>>(
      args?: SelectSubset<T, WorkspaceDeleteManyArgs<ExtArgs>>
    ): Prisma.PrismaPromise<BatchPayload>

    /**
     * Update zero or more Workspaces.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {WorkspaceUpdateManyArgs} args - Arguments to update one or more rows.
     * @example
     * // Update many Workspaces
     * const workspace = await prisma.workspace.updateMany({
     *   where: {
     *     // ... provide filter here
     *   },
     *   data: {
     *     // ... provide data here
     *   }
     * })
     * 
    **/
    updateMany<T extends WorkspaceUpdateManyArgs<ExtArgs>>(
      args: SelectSubset<T, WorkspaceUpdateManyArgs<ExtArgs>>
    ): Prisma.PrismaPromise<BatchPayload>

    /**
     * Create or update one Workspace.
     * @param {WorkspaceUpsertArgs} args - Arguments to update or create a Workspace.
     * @example
     * // Update or create a Workspace
     * const workspace = await prisma.workspace.upsert({
     *   create: {
     *     // ... data to create a Workspace
     *   },
     *   update: {
     *     // ... in case it already exists, update
     *   },
     *   where: {
     *     // ... the filter for the Workspace we want to update
     *   }
     * })
    **/
    upsert<T extends WorkspaceUpsertArgs<ExtArgs>>(
      args: SelectSubset<T, WorkspaceUpsertArgs<ExtArgs>>
    ): Prisma__WorkspaceClient<$Types.GetResult<WorkspacePayload<ExtArgs>, T, 'upsert', never>, never, ExtArgs>

    /**
     * Count the number of Workspaces.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {WorkspaceCountArgs} args - Arguments to filter Workspaces to count.
     * @example
     * // Count the number of Workspaces
     * const count = await prisma.workspace.count({
     *   where: {
     *     // ... the filter for the Workspaces we want to count
     *   }
     * })
    **/
    count<T extends WorkspaceCountArgs>(
      args?: Subset<T, WorkspaceCountArgs>,
    ): Prisma.PrismaPromise<
      T extends $Utils.Record<'select', any>
        ? T['select'] extends true
          ? number
          : GetScalarType<T['select'], WorkspaceCountAggregateOutputType>
        : number
    >

    /**
     * Allows you to perform aggregations operations on a Workspace.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {WorkspaceAggregateArgs} args - Select which aggregations you would like to apply and on what fields.
     * @example
     * // Ordered by age ascending
     * // Where email contains prisma.io
     * // Limited to the 10 users
     * const aggregations = await prisma.user.aggregate({
     *   _avg: {
     *     age: true,
     *   },
     *   where: {
     *     email: {
     *       contains: "prisma.io",
     *     },
     *   },
     *   orderBy: {
     *     age: "asc",
     *   },
     *   take: 10,
     * })
    **/
    aggregate<T extends WorkspaceAggregateArgs>(args: Subset<T, WorkspaceAggregateArgs>): Prisma.PrismaPromise<GetWorkspaceAggregateType<T>>

    /**
     * Group by Workspace.
     * Note, that providing `undefined` is treated as the value not being there.
     * Read more here: https://pris.ly/d/null-undefined
     * @param {WorkspaceGroupByArgs} args - Group by arguments.
     * @example
     * // Group by city, order by createdAt, get count
     * const result = await prisma.user.groupBy({
     *   by: ['city', 'createdAt'],
     *   orderBy: {
     *     createdAt: true
     *   },
     *   _count: {
     *     _all: true
     *   },
     * })
     * 
    **/
    groupBy<
      T extends WorkspaceGroupByArgs,
      HasSelectOrTake extends Or<
        Extends<'skip', Keys<T>>,
        Extends<'take', Keys<T>>
      >,
      OrderByArg extends True extends HasSelectOrTake
        ? { orderBy: WorkspaceGroupByArgs['orderBy'] }
        : { orderBy?: WorkspaceGroupByArgs['orderBy'] },
      OrderFields extends ExcludeUnderscoreKeys<Keys<MaybeTupleToUnion<T['orderBy']>>>,
      ByFields extends TupleToUnion<T['by']>,
      ByValid extends Has<ByFields, OrderFields>,
      HavingFields extends GetHavingFields<T['having']>,
      HavingValid extends Has<ByFields, HavingFields>,
      ByEmpty extends T['by'] extends never[] ? True : False,
      InputErrors extends ByEmpty extends True
      ? `Error: "by" must not be empty.`
      : HavingValid extends False
      ? {
          [P in HavingFields]: P extends ByFields
            ? never
            : P extends string
            ? `Error: Field "${P}" used in "having" needs to be provided in "by".`
            : [
                Error,
                'Field ',
                P,
                ` in "having" needs to be provided in "by"`,
              ]
        }[HavingFields]
      : 'take' extends Keys<T>
      ? 'orderBy' extends Keys<T>
        ? ByValid extends True
          ? {}
          : {
              [P in OrderFields]: P extends ByFields
                ? never
                : `Error: Field "${P}" in "orderBy" needs to be provided in "by"`
            }[OrderFields]
        : 'Error: If you provide "take", you also need to provide "orderBy"'
      : 'skip' extends Keys<T>
      ? 'orderBy' extends Keys<T>
        ? ByValid extends True
          ? {}
          : {
              [P in OrderFields]: P extends ByFields
                ? never
                : `Error: Field "${P}" in "orderBy" needs to be provided in "by"`
            }[OrderFields]
        : 'Error: If you provide "skip", you also need to provide "orderBy"'
      : ByValid extends True
      ? {}
      : {
          [P in OrderFields]: P extends ByFields
            ? never
            : `Error: Field "${P}" in "orderBy" needs to be provided in "by"`
        }[OrderFields]
    >(args: SubsetIntersection<T, WorkspaceGroupByArgs, OrderByArg> & InputErrors): {} extends InputErrors ? GetWorkspaceGroupByPayload<T> : Prisma.PrismaPromise<InputErrors>

  }

  /**
   * The delegate class that acts as a "Promise-like" for Workspace.
   * Why is this prefixed with `Prisma__`?
   * Because we want to prevent naming conflicts as mentioned in
   * https://github.com/prisma/prisma-client-js/issues/707
   */
  export class Prisma__WorkspaceClient<T, Null = never, ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> implements Prisma.PrismaPromise<T> {
    private readonly _dmmf;
    private readonly _queryType;
    private readonly _rootField;
    private readonly _clientMethod;
    private readonly _args;
    private readonly _dataPath;
    private readonly _errorFormat;
    private readonly _measurePerformance?;
    private _isList;
    private _callsite;
    private _requestPromise?;
    readonly [Symbol.toStringTag]: 'PrismaPromise';
    constructor(_dmmf: runtime.DMMFClass, _queryType: 'query' | 'mutation', _rootField: string, _clientMethod: string, _args: any, _dataPath: string[], _errorFormat: ErrorFormat, _measurePerformance?: boolean | undefined, _isList?: boolean);

    vaults<T extends Workspace$vaultsArgs<ExtArgs> = {}>(args?: Subset<T, Workspace$vaultsArgs<ExtArgs>>): Prisma.PrismaPromise<$Types.GetResult<DVaultPayload<ExtArgs>, T, 'findMany', never>| Null>;

    private get _document();
    /**
     * Attaches callbacks for the resolution and/or rejection of the Promise.
     * @param onfulfilled The callback to execute when the Promise is resolved.
     * @param onrejected The callback to execute when the Promise is rejected.
     * @returns A Promise for the completion of which ever callback is executed.
     */
    then<TResult1 = T, TResult2 = never>(onfulfilled?: ((value: T) => TResult1 | PromiseLike<TResult1>) | undefined | null, onrejected?: ((reason: any) => TResult2 | PromiseLike<TResult2>) | undefined | null): Promise<TResult1 | TResult2>;
    /**
     * Attaches a callback for only the rejection of the Promise.
     * @param onrejected The callback to execute when the Promise is rejected.
     * @returns A Promise for the completion of the callback.
     */
    catch<TResult = never>(onrejected?: ((reason: any) => TResult | PromiseLike<TResult>) | undefined | null): Promise<T | TResult>;
    /**
     * Attaches a callback that is invoked when the Promise is settled (fulfilled or rejected). The
     * resolved value cannot be modified from the callback.
     * @param onfinally The callback to execute when the Promise is settled (fulfilled or rejected).
     * @returns A Promise for the completion of the callback.
     */
    finally(onfinally?: (() => void) | undefined | null): Promise<T>;
  }



  // Custom InputTypes

  /**
   * Workspace base type for findUnique actions
   */
  export type WorkspaceFindUniqueArgsBase<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Workspace
     */
    select?: WorkspaceSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: WorkspaceInclude<ExtArgs> | null
    /**
     * Filter, which Workspace to fetch.
     */
    where: WorkspaceWhereUniqueInput
  }

  /**
   * Workspace findUnique
   */
  export interface WorkspaceFindUniqueArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> extends WorkspaceFindUniqueArgsBase<ExtArgs> {
   /**
    * Throw an Error if query returns no results
    * @deprecated since 4.0.0: use `findUniqueOrThrow` method instead
    */
    rejectOnNotFound?: RejectOnNotFound
  }
      

  /**
   * Workspace findUniqueOrThrow
   */
  export type WorkspaceFindUniqueOrThrowArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Workspace
     */
    select?: WorkspaceSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: WorkspaceInclude<ExtArgs> | null
    /**
     * Filter, which Workspace to fetch.
     */
    where: WorkspaceWhereUniqueInput
  }


  /**
   * Workspace base type for findFirst actions
   */
  export type WorkspaceFindFirstArgsBase<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Workspace
     */
    select?: WorkspaceSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: WorkspaceInclude<ExtArgs> | null
    /**
     * Filter, which Workspace to fetch.
     */
    where?: WorkspaceWhereInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/sorting Sorting Docs}
     * 
     * Determine the order of Workspaces to fetch.
     */
    orderBy?: Enumerable<WorkspaceOrderByWithRelationInput>
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination#cursor-based-pagination Cursor Docs}
     * 
     * Sets the position for searching for Workspaces.
     */
    cursor?: WorkspaceWhereUniqueInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Take `±n` Workspaces from the position of the cursor.
     */
    take?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Skip the first `n` Workspaces.
     */
    skip?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/distinct Distinct Docs}
     * 
     * Filter by unique combinations of Workspaces.
     */
    distinct?: Enumerable<WorkspaceScalarFieldEnum>
  }

  /**
   * Workspace findFirst
   */
  export interface WorkspaceFindFirstArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> extends WorkspaceFindFirstArgsBase<ExtArgs> {
   /**
    * Throw an Error if query returns no results
    * @deprecated since 4.0.0: use `findFirstOrThrow` method instead
    */
    rejectOnNotFound?: RejectOnNotFound
  }
      

  /**
   * Workspace findFirstOrThrow
   */
  export type WorkspaceFindFirstOrThrowArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Workspace
     */
    select?: WorkspaceSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: WorkspaceInclude<ExtArgs> | null
    /**
     * Filter, which Workspace to fetch.
     */
    where?: WorkspaceWhereInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/sorting Sorting Docs}
     * 
     * Determine the order of Workspaces to fetch.
     */
    orderBy?: Enumerable<WorkspaceOrderByWithRelationInput>
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination#cursor-based-pagination Cursor Docs}
     * 
     * Sets the position for searching for Workspaces.
     */
    cursor?: WorkspaceWhereUniqueInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Take `±n` Workspaces from the position of the cursor.
     */
    take?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Skip the first `n` Workspaces.
     */
    skip?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/distinct Distinct Docs}
     * 
     * Filter by unique combinations of Workspaces.
     */
    distinct?: Enumerable<WorkspaceScalarFieldEnum>
  }


  /**
   * Workspace findMany
   */
  export type WorkspaceFindManyArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Workspace
     */
    select?: WorkspaceSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: WorkspaceInclude<ExtArgs> | null
    /**
     * Filter, which Workspaces to fetch.
     */
    where?: WorkspaceWhereInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/sorting Sorting Docs}
     * 
     * Determine the order of Workspaces to fetch.
     */
    orderBy?: Enumerable<WorkspaceOrderByWithRelationInput>
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination#cursor-based-pagination Cursor Docs}
     * 
     * Sets the position for listing Workspaces.
     */
    cursor?: WorkspaceWhereUniqueInput
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Take `±n` Workspaces from the position of the cursor.
     */
    take?: number
    /**
     * {@link https://www.prisma.io/docs/concepts/components/prisma-client/pagination Pagination Docs}
     * 
     * Skip the first `n` Workspaces.
     */
    skip?: number
    distinct?: Enumerable<WorkspaceScalarFieldEnum>
  }


  /**
   * Workspace create
   */
  export type WorkspaceCreateArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Workspace
     */
    select?: WorkspaceSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: WorkspaceInclude<ExtArgs> | null
    /**
     * The data needed to create a Workspace.
     */
    data: XOR<WorkspaceCreateInput, WorkspaceUncheckedCreateInput>
  }


  /**
   * Workspace update
   */
  export type WorkspaceUpdateArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Workspace
     */
    select?: WorkspaceSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: WorkspaceInclude<ExtArgs> | null
    /**
     * The data needed to update a Workspace.
     */
    data: XOR<WorkspaceUpdateInput, WorkspaceUncheckedUpdateInput>
    /**
     * Choose, which Workspace to update.
     */
    where: WorkspaceWhereUniqueInput
  }


  /**
   * Workspace updateMany
   */
  export type WorkspaceUpdateManyArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * The data used to update Workspaces.
     */
    data: XOR<WorkspaceUpdateManyMutationInput, WorkspaceUncheckedUpdateManyInput>
    /**
     * Filter which Workspaces to update
     */
    where?: WorkspaceWhereInput
  }


  /**
   * Workspace upsert
   */
  export type WorkspaceUpsertArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Workspace
     */
    select?: WorkspaceSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: WorkspaceInclude<ExtArgs> | null
    /**
     * The filter to search for the Workspace to update in case it exists.
     */
    where: WorkspaceWhereUniqueInput
    /**
     * In case the Workspace found by the `where` argument doesn't exist, create a new Workspace with this data.
     */
    create: XOR<WorkspaceCreateInput, WorkspaceUncheckedCreateInput>
    /**
     * In case the Workspace was found with the provided `where` argument, update it with this data.
     */
    update: XOR<WorkspaceUpdateInput, WorkspaceUncheckedUpdateInput>
  }


  /**
   * Workspace delete
   */
  export type WorkspaceDeleteArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Workspace
     */
    select?: WorkspaceSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: WorkspaceInclude<ExtArgs> | null
    /**
     * Filter which Workspace to delete.
     */
    where: WorkspaceWhereUniqueInput
  }


  /**
   * Workspace deleteMany
   */
  export type WorkspaceDeleteManyArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Filter which Workspaces to delete
     */
    where?: WorkspaceWhereInput
  }


  /**
   * Workspace.vaults
   */
  export type Workspace$vaultsArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the DVault
     */
    select?: DVaultSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: DVaultInclude<ExtArgs> | null
    where?: DVaultWhereInput
    orderBy?: Enumerable<DVaultOrderByWithRelationInput>
    cursor?: DVaultWhereUniqueInput
    take?: number
    skip?: number
    distinct?: Enumerable<DVaultScalarFieldEnum>
  }


  /**
   * Workspace without action
   */
  export type WorkspaceArgs<ExtArgs extends $Extensions.Args = $Extensions.DefaultArgs> = {
    /**
     * Select specific fields to fetch from the Workspace
     */
    select?: WorkspaceSelect<ExtArgs> | null
    /**
     * Choose, which related nodes to fetch as well.
     */
    include?: WorkspaceInclude<ExtArgs> | null
  }



  /**
   * Enums
   */

  export const TransactionIsolationLevel: {
    Serializable: 'Serializable'
  };

  export type TransactionIsolationLevel = (typeof TransactionIsolationLevel)[keyof typeof TransactionIsolationLevel]


  export const NoteScalarFieldEnum: {
    id: 'id',
    fname: 'fname',
    title: 'title',
    updated: 'updated',
    created: 'created',
    stub: 'stub',
    dVaultId: 'dVaultId'
  };

  export type NoteScalarFieldEnum = (typeof NoteScalarFieldEnum)[keyof typeof NoteScalarFieldEnum]


  export const DVaultScalarFieldEnum: {
    id: 'id',
    name: 'name',
    fsPath: 'fsPath',
    wsRoot: 'wsRoot'
  };

  export type DVaultScalarFieldEnum = (typeof DVaultScalarFieldEnum)[keyof typeof DVaultScalarFieldEnum]


  export const WorkspaceScalarFieldEnum: {
    wsRoot: 'wsRoot',
    prismaSchemaVersion: 'prismaSchemaVersion'
  };

  export type WorkspaceScalarFieldEnum = (typeof WorkspaceScalarFieldEnum)[keyof typeof WorkspaceScalarFieldEnum]


  export const SortOrder: {
    asc: 'asc',
    desc: 'desc'
  };

  export type SortOrder = (typeof SortOrder)[keyof typeof SortOrder]


  export const NullsOrder: {
    first: 'first',
    last: 'last'
  };

  export type NullsOrder = (typeof NullsOrder)[keyof typeof NullsOrder]


  /**
   * Deep Input Types
   */


  export type NoteWhereInput = {
    AND?: Enumerable<NoteWhereInput>
    OR?: Enumerable<NoteWhereInput>
    NOT?: Enumerable<NoteWhereInput>
    id?: StringFilter | string
    fname?: StringNullableFilter | string | null
    title?: StringNullableFilter | string | null
    updated?: IntNullableFilter | number | null
    created?: IntNullableFilter | number | null
    stub?: BoolNullableFilter | boolean | null
    dVaultId?: IntFilter | number
    vault?: XOR<DVaultRelationFilter, DVaultWhereInput>
  }

  export type NoteOrderByWithRelationInput = {
    id?: SortOrder
    fname?: SortOrderInput | SortOrder
    title?: SortOrderInput | SortOrder
    updated?: SortOrderInput | SortOrder
    created?: SortOrderInput | SortOrder
    stub?: SortOrderInput | SortOrder
    dVaultId?: SortOrder
    vault?: DVaultOrderByWithRelationInput
  }

  export type NoteWhereUniqueInput = {
    id?: string
  }

  export type NoteOrderByWithAggregationInput = {
    id?: SortOrder
    fname?: SortOrderInput | SortOrder
    title?: SortOrderInput | SortOrder
    updated?: SortOrderInput | SortOrder
    created?: SortOrderInput | SortOrder
    stub?: SortOrderInput | SortOrder
    dVaultId?: SortOrder
    _count?: NoteCountOrderByAggregateInput
    _avg?: NoteAvgOrderByAggregateInput
    _max?: NoteMaxOrderByAggregateInput
    _min?: NoteMinOrderByAggregateInput
    _sum?: NoteSumOrderByAggregateInput
  }

  export type NoteScalarWhereWithAggregatesInput = {
    AND?: Enumerable<NoteScalarWhereWithAggregatesInput>
    OR?: Enumerable<NoteScalarWhereWithAggregatesInput>
    NOT?: Enumerable<NoteScalarWhereWithAggregatesInput>
    id?: StringWithAggregatesFilter | string
    fname?: StringNullableWithAggregatesFilter | string | null
    title?: StringNullableWithAggregatesFilter | string | null
    updated?: IntNullableWithAggregatesFilter | number | null
    created?: IntNullableWithAggregatesFilter | number | null
    stub?: BoolNullableWithAggregatesFilter | boolean | null
    dVaultId?: IntWithAggregatesFilter | number
  }

  export type DVaultWhereInput = {
    AND?: Enumerable<DVaultWhereInput>
    OR?: Enumerable<DVaultWhereInput>
    NOT?: Enumerable<DVaultWhereInput>
    id?: IntFilter | number
    name?: StringNullableFilter | string | null
    fsPath?: StringFilter | string
    wsRoot?: StringFilter | string
    workspace?: XOR<WorkspaceRelationFilter, WorkspaceWhereInput>
    Note?: NoteListRelationFilter
  }

  export type DVaultOrderByWithRelationInput = {
    id?: SortOrder
    name?: SortOrderInput | SortOrder
    fsPath?: SortOrder
    wsRoot?: SortOrder
    workspace?: WorkspaceOrderByWithRelationInput
    Note?: NoteOrderByRelationAggregateInput
  }

  export type DVaultWhereUniqueInput = {
    id?: number
    name?: string
    wsRoot_fsPath?: DVaultWsRootFsPathCompoundUniqueInput
  }

  export type DVaultOrderByWithAggregationInput = {
    id?: SortOrder
    name?: SortOrderInput | SortOrder
    fsPath?: SortOrder
    wsRoot?: SortOrder
    _count?: DVaultCountOrderByAggregateInput
    _avg?: DVaultAvgOrderByAggregateInput
    _max?: DVaultMaxOrderByAggregateInput
    _min?: DVaultMinOrderByAggregateInput
    _sum?: DVaultSumOrderByAggregateInput
  }

  export type DVaultScalarWhereWithAggregatesInput = {
    AND?: Enumerable<DVaultScalarWhereWithAggregatesInput>
    OR?: Enumerable<DVaultScalarWhereWithAggregatesInput>
    NOT?: Enumerable<DVaultScalarWhereWithAggregatesInput>
    id?: IntWithAggregatesFilter | number
    name?: StringNullableWithAggregatesFilter | string | null
    fsPath?: StringWithAggregatesFilter | string
    wsRoot?: StringWithAggregatesFilter | string
  }

  export type WorkspaceWhereInput = {
    AND?: Enumerable<WorkspaceWhereInput>
    OR?: Enumerable<WorkspaceWhereInput>
    NOT?: Enumerable<WorkspaceWhereInput>
    wsRoot?: StringFilter | string
    prismaSchemaVersion?: IntFilter | number
    vaults?: DVaultListRelationFilter
  }

  export type WorkspaceOrderByWithRelationInput = {
    wsRoot?: SortOrder
    prismaSchemaVersion?: SortOrder
    vaults?: DVaultOrderByRelationAggregateInput
  }

  export type WorkspaceWhereUniqueInput = {
    wsRoot?: string
  }

  export type WorkspaceOrderByWithAggregationInput = {
    wsRoot?: SortOrder
    prismaSchemaVersion?: SortOrder
    _count?: WorkspaceCountOrderByAggregateInput
    _avg?: WorkspaceAvgOrderByAggregateInput
    _max?: WorkspaceMaxOrderByAggregateInput
    _min?: WorkspaceMinOrderByAggregateInput
    _sum?: WorkspaceSumOrderByAggregateInput
  }

  export type WorkspaceScalarWhereWithAggregatesInput = {
    AND?: Enumerable<WorkspaceScalarWhereWithAggregatesInput>
    OR?: Enumerable<WorkspaceScalarWhereWithAggregatesInput>
    NOT?: Enumerable<WorkspaceScalarWhereWithAggregatesInput>
    wsRoot?: StringWithAggregatesFilter | string
    prismaSchemaVersion?: IntWithAggregatesFilter | number
  }

  export type NoteCreateInput = {
    id: string
    fname?: string | null
    title?: string | null
    updated?: number | null
    created?: number | null
    stub?: boolean | null
    vault: DVaultCreateNestedOneWithoutNoteInput
  }

  export type NoteUncheckedCreateInput = {
    id: string
    fname?: string | null
    title?: string | null
    updated?: number | null
    created?: number | null
    stub?: boolean | null
    dVaultId: number
  }

  export type NoteUpdateInput = {
    id?: StringFieldUpdateOperationsInput | string
    fname?: NullableStringFieldUpdateOperationsInput | string | null
    title?: NullableStringFieldUpdateOperationsInput | string | null
    updated?: NullableIntFieldUpdateOperationsInput | number | null
    created?: NullableIntFieldUpdateOperationsInput | number | null
    stub?: NullableBoolFieldUpdateOperationsInput | boolean | null
    vault?: DVaultUpdateOneRequiredWithoutNoteNestedInput
  }

  export type NoteUncheckedUpdateInput = {
    id?: StringFieldUpdateOperationsInput | string
    fname?: NullableStringFieldUpdateOperationsInput | string | null
    title?: NullableStringFieldUpdateOperationsInput | string | null
    updated?: NullableIntFieldUpdateOperationsInput | number | null
    created?: NullableIntFieldUpdateOperationsInput | number | null
    stub?: NullableBoolFieldUpdateOperationsInput | boolean | null
    dVaultId?: IntFieldUpdateOperationsInput | number
  }

  export type NoteUpdateManyMutationInput = {
    id?: StringFieldUpdateOperationsInput | string
    fname?: NullableStringFieldUpdateOperationsInput | string | null
    title?: NullableStringFieldUpdateOperationsInput | string | null
    updated?: NullableIntFieldUpdateOperationsInput | number | null
    created?: NullableIntFieldUpdateOperationsInput | number | null
    stub?: NullableBoolFieldUpdateOperationsInput | boolean | null
  }

  export type NoteUncheckedUpdateManyInput = {
    id?: StringFieldUpdateOperationsInput | string
    fname?: NullableStringFieldUpdateOperationsInput | string | null
    title?: NullableStringFieldUpdateOperationsInput | string | null
    updated?: NullableIntFieldUpdateOperationsInput | number | null
    created?: NullableIntFieldUpdateOperationsInput | number | null
    stub?: NullableBoolFieldUpdateOperationsInput | boolean | null
    dVaultId?: IntFieldUpdateOperationsInput | number
  }

  export type DVaultCreateInput = {
    name?: string | null
    fsPath: string
    workspace: WorkspaceCreateNestedOneWithoutVaultsInput
    Note?: NoteCreateNestedManyWithoutVaultInput
  }

  export type DVaultUncheckedCreateInput = {
    id?: number
    name?: string | null
    fsPath: string
    wsRoot: string
    Note?: NoteUncheckedCreateNestedManyWithoutVaultInput
  }

  export type DVaultUpdateInput = {
    name?: NullableStringFieldUpdateOperationsInput | string | null
    fsPath?: StringFieldUpdateOperationsInput | string
    workspace?: WorkspaceUpdateOneRequiredWithoutVaultsNestedInput
    Note?: NoteUpdateManyWithoutVaultNestedInput
  }

  export type DVaultUncheckedUpdateInput = {
    id?: IntFieldUpdateOperationsInput | number
    name?: NullableStringFieldUpdateOperationsInput | string | null
    fsPath?: StringFieldUpdateOperationsInput | string
    wsRoot?: StringFieldUpdateOperationsInput | string
    Note?: NoteUncheckedUpdateManyWithoutVaultNestedInput
  }

  export type DVaultUpdateManyMutationInput = {
    name?: NullableStringFieldUpdateOperationsInput | string | null
    fsPath?: StringFieldUpdateOperationsInput | string
  }

  export type DVaultUncheckedUpdateManyInput = {
    id?: IntFieldUpdateOperationsInput | number
    name?: NullableStringFieldUpdateOperationsInput | string | null
    fsPath?: StringFieldUpdateOperationsInput | string
    wsRoot?: StringFieldUpdateOperationsInput | string
  }

  export type WorkspaceCreateInput = {
    wsRoot: string
    prismaSchemaVersion: number
    vaults?: DVaultCreateNestedManyWithoutWorkspaceInput
  }

  export type WorkspaceUncheckedCreateInput = {
    wsRoot: string
    prismaSchemaVersion: number
    vaults?: DVaultUncheckedCreateNestedManyWithoutWorkspaceInput
  }

  export type WorkspaceUpdateInput = {
    wsRoot?: StringFieldUpdateOperationsInput | string
    prismaSchemaVersion?: IntFieldUpdateOperationsInput | number
    vaults?: DVaultUpdateManyWithoutWorkspaceNestedInput
  }

  export type WorkspaceUncheckedUpdateInput = {
    wsRoot?: StringFieldUpdateOperationsInput | string
    prismaSchemaVersion?: IntFieldUpdateOperationsInput | number
    vaults?: DVaultUncheckedUpdateManyWithoutWorkspaceNestedInput
  }

  export type WorkspaceUpdateManyMutationInput = {
    wsRoot?: StringFieldUpdateOperationsInput | string
    prismaSchemaVersion?: IntFieldUpdateOperationsInput | number
  }

  export type WorkspaceUncheckedUpdateManyInput = {
    wsRoot?: StringFieldUpdateOperationsInput | string
    prismaSchemaVersion?: IntFieldUpdateOperationsInput | number
  }

  export type StringFilter = {
    equals?: string
    in?: Enumerable<string> | string
    notIn?: Enumerable<string> | string
    lt?: string
    lte?: string
    gt?: string
    gte?: string
    contains?: string
    startsWith?: string
    endsWith?: string
    not?: NestedStringFilter | string
  }

  export type StringNullableFilter = {
    equals?: string | null
    in?: Enumerable<string> | string | null
    notIn?: Enumerable<string> | string | null
    lt?: string
    lte?: string
    gt?: string
    gte?: string
    contains?: string
    startsWith?: string
    endsWith?: string
    not?: NestedStringNullableFilter | string | null
  }

  export type IntNullableFilter = {
    equals?: number | null
    in?: Enumerable<number> | number | null
    notIn?: Enumerable<number> | number | null
    lt?: number
    lte?: number
    gt?: number
    gte?: number
    not?: NestedIntNullableFilter | number | null
  }

  export type BoolNullableFilter = {
    equals?: boolean | null
    not?: NestedBoolNullableFilter | boolean | null
  }

  export type IntFilter = {
    equals?: number
    in?: Enumerable<number> | number
    notIn?: Enumerable<number> | number
    lt?: number
    lte?: number
    gt?: number
    gte?: number
    not?: NestedIntFilter | number
  }

  export type DVaultRelationFilter = {
    is?: DVaultWhereInput | null
    isNot?: DVaultWhereInput | null
  }

  export type SortOrderInput = {
    sort: SortOrder
    nulls?: NullsOrder
  }

  export type NoteCountOrderByAggregateInput = {
    id?: SortOrder
    fname?: SortOrder
    title?: SortOrder
    updated?: SortOrder
    created?: SortOrder
    stub?: SortOrder
    dVaultId?: SortOrder
  }

  export type NoteAvgOrderByAggregateInput = {
    updated?: SortOrder
    created?: SortOrder
    dVaultId?: SortOrder
  }

  export type NoteMaxOrderByAggregateInput = {
    id?: SortOrder
    fname?: SortOrder
    title?: SortOrder
    updated?: SortOrder
    created?: SortOrder
    stub?: SortOrder
    dVaultId?: SortOrder
  }

  export type NoteMinOrderByAggregateInput = {
    id?: SortOrder
    fname?: SortOrder
    title?: SortOrder
    updated?: SortOrder
    created?: SortOrder
    stub?: SortOrder
    dVaultId?: SortOrder
  }

  export type NoteSumOrderByAggregateInput = {
    updated?: SortOrder
    created?: SortOrder
    dVaultId?: SortOrder
  }

  export type StringWithAggregatesFilter = {
    equals?: string
    in?: Enumerable<string> | string
    notIn?: Enumerable<string> | string
    lt?: string
    lte?: string
    gt?: string
    gte?: string
    contains?: string
    startsWith?: string
    endsWith?: string
    not?: NestedStringWithAggregatesFilter | string
    _count?: NestedIntFilter
    _min?: NestedStringFilter
    _max?: NestedStringFilter
  }

  export type StringNullableWithAggregatesFilter = {
    equals?: string | null
    in?: Enumerable<string> | string | null
    notIn?: Enumerable<string> | string | null
    lt?: string
    lte?: string
    gt?: string
    gte?: string
    contains?: string
    startsWith?: string
    endsWith?: string
    not?: NestedStringNullableWithAggregatesFilter | string | null
    _count?: NestedIntNullableFilter
    _min?: NestedStringNullableFilter
    _max?: NestedStringNullableFilter
  }

  export type IntNullableWithAggregatesFilter = {
    equals?: number | null
    in?: Enumerable<number> | number | null
    notIn?: Enumerable<number> | number | null
    lt?: number
    lte?: number
    gt?: number
    gte?: number
    not?: NestedIntNullableWithAggregatesFilter | number | null
    _count?: NestedIntNullableFilter
    _avg?: NestedFloatNullableFilter
    _sum?: NestedIntNullableFilter
    _min?: NestedIntNullableFilter
    _max?: NestedIntNullableFilter
  }

  export type BoolNullableWithAggregatesFilter = {
    equals?: boolean | null
    not?: NestedBoolNullableWithAggregatesFilter | boolean | null
    _count?: NestedIntNullableFilter
    _min?: NestedBoolNullableFilter
    _max?: NestedBoolNullableFilter
  }

  export type IntWithAggregatesFilter = {
    equals?: number
    in?: Enumerable<number> | number
    notIn?: Enumerable<number> | number
    lt?: number
    lte?: number
    gt?: number
    gte?: number
    not?: NestedIntWithAggregatesFilter | number
    _count?: NestedIntFilter
    _avg?: NestedFloatFilter
    _sum?: NestedIntFilter
    _min?: NestedIntFilter
    _max?: NestedIntFilter
  }

  export type WorkspaceRelationFilter = {
    is?: WorkspaceWhereInput | null
    isNot?: WorkspaceWhereInput | null
  }

  export type NoteListRelationFilter = {
    every?: NoteWhereInput
    some?: NoteWhereInput
    none?: NoteWhereInput
  }

  export type NoteOrderByRelationAggregateInput = {
    _count?: SortOrder
  }

  export type DVaultWsRootFsPathCompoundUniqueInput = {
    wsRoot: string
    fsPath: string
  }

  export type DVaultCountOrderByAggregateInput = {
    id?: SortOrder
    name?: SortOrder
    fsPath?: SortOrder
    wsRoot?: SortOrder
  }

  export type DVaultAvgOrderByAggregateInput = {
    id?: SortOrder
  }

  export type DVaultMaxOrderByAggregateInput = {
    id?: SortOrder
    name?: SortOrder
    fsPath?: SortOrder
    wsRoot?: SortOrder
  }

  export type DVaultMinOrderByAggregateInput = {
    id?: SortOrder
    name?: SortOrder
    fsPath?: SortOrder
    wsRoot?: SortOrder
  }

  export type DVaultSumOrderByAggregateInput = {
    id?: SortOrder
  }

  export type DVaultListRelationFilter = {
    every?: DVaultWhereInput
    some?: DVaultWhereInput
    none?: DVaultWhereInput
  }

  export type DVaultOrderByRelationAggregateInput = {
    _count?: SortOrder
  }

  export type WorkspaceCountOrderByAggregateInput = {
    wsRoot?: SortOrder
    prismaSchemaVersion?: SortOrder
  }

  export type WorkspaceAvgOrderByAggregateInput = {
    prismaSchemaVersion?: SortOrder
  }

  export type WorkspaceMaxOrderByAggregateInput = {
    wsRoot?: SortOrder
    prismaSchemaVersion?: SortOrder
  }

  export type WorkspaceMinOrderByAggregateInput = {
    wsRoot?: SortOrder
    prismaSchemaVersion?: SortOrder
  }

  export type WorkspaceSumOrderByAggregateInput = {
    prismaSchemaVersion?: SortOrder
  }

  export type DVaultCreateNestedOneWithoutNoteInput = {
    create?: XOR<DVaultCreateWithoutNoteInput, DVaultUncheckedCreateWithoutNoteInput>
    connectOrCreate?: DVaultCreateOrConnectWithoutNoteInput
    connect?: DVaultWhereUniqueInput
  }

  export type StringFieldUpdateOperationsInput = {
    set?: string
  }

  export type NullableStringFieldUpdateOperationsInput = {
    set?: string | null
  }

  export type NullableIntFieldUpdateOperationsInput = {
    set?: number | null
    increment?: number
    decrement?: number
    multiply?: number
    divide?: number
  }

  export type NullableBoolFieldUpdateOperationsInput = {
    set?: boolean | null
  }

  export type DVaultUpdateOneRequiredWithoutNoteNestedInput = {
    create?: XOR<DVaultCreateWithoutNoteInput, DVaultUncheckedCreateWithoutNoteInput>
    connectOrCreate?: DVaultCreateOrConnectWithoutNoteInput
    upsert?: DVaultUpsertWithoutNoteInput
    connect?: DVaultWhereUniqueInput
    update?: XOR<DVaultUpdateWithoutNoteInput, DVaultUncheckedUpdateWithoutNoteInput>
  }

  export type IntFieldUpdateOperationsInput = {
    set?: number
    increment?: number
    decrement?: number
    multiply?: number
    divide?: number
  }

  export type WorkspaceCreateNestedOneWithoutVaultsInput = {
    create?: XOR<WorkspaceCreateWithoutVaultsInput, WorkspaceUncheckedCreateWithoutVaultsInput>
    connectOrCreate?: WorkspaceCreateOrConnectWithoutVaultsInput
    connect?: WorkspaceWhereUniqueInput
  }

  export type NoteCreateNestedManyWithoutVaultInput = {
    create?: XOR<Enumerable<NoteCreateWithoutVaultInput>, Enumerable<NoteUncheckedCreateWithoutVaultInput>>
    connectOrCreate?: Enumerable<NoteCreateOrConnectWithoutVaultInput>
    connect?: Enumerable<NoteWhereUniqueInput>
  }

  export type NoteUncheckedCreateNestedManyWithoutVaultInput = {
    create?: XOR<Enumerable<NoteCreateWithoutVaultInput>, Enumerable<NoteUncheckedCreateWithoutVaultInput>>
    connectOrCreate?: Enumerable<NoteCreateOrConnectWithoutVaultInput>
    connect?: Enumerable<NoteWhereUniqueInput>
  }

  export type WorkspaceUpdateOneRequiredWithoutVaultsNestedInput = {
    create?: XOR<WorkspaceCreateWithoutVaultsInput, WorkspaceUncheckedCreateWithoutVaultsInput>
    connectOrCreate?: WorkspaceCreateOrConnectWithoutVaultsInput
    upsert?: WorkspaceUpsertWithoutVaultsInput
    connect?: WorkspaceWhereUniqueInput
    update?: XOR<WorkspaceUpdateWithoutVaultsInput, WorkspaceUncheckedUpdateWithoutVaultsInput>
  }

  export type NoteUpdateManyWithoutVaultNestedInput = {
    create?: XOR<Enumerable<NoteCreateWithoutVaultInput>, Enumerable<NoteUncheckedCreateWithoutVaultInput>>
    connectOrCreate?: Enumerable<NoteCreateOrConnectWithoutVaultInput>
    upsert?: Enumerable<NoteUpsertWithWhereUniqueWithoutVaultInput>
    set?: Enumerable<NoteWhereUniqueInput>
    disconnect?: Enumerable<NoteWhereUniqueInput>
    delete?: Enumerable<NoteWhereUniqueInput>
    connect?: Enumerable<NoteWhereUniqueInput>
    update?: Enumerable<NoteUpdateWithWhereUniqueWithoutVaultInput>
    updateMany?: Enumerable<NoteUpdateManyWithWhereWithoutVaultInput>
    deleteMany?: Enumerable<NoteScalarWhereInput>
  }

  export type NoteUncheckedUpdateManyWithoutVaultNestedInput = {
    create?: XOR<Enumerable<NoteCreateWithoutVaultInput>, Enumerable<NoteUncheckedCreateWithoutVaultInput>>
    connectOrCreate?: Enumerable<NoteCreateOrConnectWithoutVaultInput>
    upsert?: Enumerable<NoteUpsertWithWhereUniqueWithoutVaultInput>
    set?: Enumerable<NoteWhereUniqueInput>
    disconnect?: Enumerable<NoteWhereUniqueInput>
    delete?: Enumerable<NoteWhereUniqueInput>
    connect?: Enumerable<NoteWhereUniqueInput>
    update?: Enumerable<NoteUpdateWithWhereUniqueWithoutVaultInput>
    updateMany?: Enumerable<NoteUpdateManyWithWhereWithoutVaultInput>
    deleteMany?: Enumerable<NoteScalarWhereInput>
  }

  export type DVaultCreateNestedManyWithoutWorkspaceInput = {
    create?: XOR<Enumerable<DVaultCreateWithoutWorkspaceInput>, Enumerable<DVaultUncheckedCreateWithoutWorkspaceInput>>
    connectOrCreate?: Enumerable<DVaultCreateOrConnectWithoutWorkspaceInput>
    connect?: Enumerable<DVaultWhereUniqueInput>
  }

  export type DVaultUncheckedCreateNestedManyWithoutWorkspaceInput = {
    create?: XOR<Enumerable<DVaultCreateWithoutWorkspaceInput>, Enumerable<DVaultUncheckedCreateWithoutWorkspaceInput>>
    connectOrCreate?: Enumerable<DVaultCreateOrConnectWithoutWorkspaceInput>
    connect?: Enumerable<DVaultWhereUniqueInput>
  }

  export type DVaultUpdateManyWithoutWorkspaceNestedInput = {
    create?: XOR<Enumerable<DVaultCreateWithoutWorkspaceInput>, Enumerable<DVaultUncheckedCreateWithoutWorkspaceInput>>
    connectOrCreate?: Enumerable<DVaultCreateOrConnectWithoutWorkspaceInput>
    upsert?: Enumerable<DVaultUpsertWithWhereUniqueWithoutWorkspaceInput>
    set?: Enumerable<DVaultWhereUniqueInput>
    disconnect?: Enumerable<DVaultWhereUniqueInput>
    delete?: Enumerable<DVaultWhereUniqueInput>
    connect?: Enumerable<DVaultWhereUniqueInput>
    update?: Enumerable<DVaultUpdateWithWhereUniqueWithoutWorkspaceInput>
    updateMany?: Enumerable<DVaultUpdateManyWithWhereWithoutWorkspaceInput>
    deleteMany?: Enumerable<DVaultScalarWhereInput>
  }

  export type DVaultUncheckedUpdateManyWithoutWorkspaceNestedInput = {
    create?: XOR<Enumerable<DVaultCreateWithoutWorkspaceInput>, Enumerable<DVaultUncheckedCreateWithoutWorkspaceInput>>
    connectOrCreate?: Enumerable<DVaultCreateOrConnectWithoutWorkspaceInput>
    upsert?: Enumerable<DVaultUpsertWithWhereUniqueWithoutWorkspaceInput>
    set?: Enumerable<DVaultWhereUniqueInput>
    disconnect?: Enumerable<DVaultWhereUniqueInput>
    delete?: Enumerable<DVaultWhereUniqueInput>
    connect?: Enumerable<DVaultWhereUniqueInput>
    update?: Enumerable<DVaultUpdateWithWhereUniqueWithoutWorkspaceInput>
    updateMany?: Enumerable<DVaultUpdateManyWithWhereWithoutWorkspaceInput>
    deleteMany?: Enumerable<DVaultScalarWhereInput>
  }

  export type NestedStringFilter = {
    equals?: string
    in?: Enumerable<string> | string
    notIn?: Enumerable<string> | string
    lt?: string
    lte?: string
    gt?: string
    gte?: string
    contains?: string
    startsWith?: string
    endsWith?: string
    not?: NestedStringFilter | string
  }

  export type NestedStringNullableFilter = {
    equals?: string | null
    in?: Enumerable<string> | string | null
    notIn?: Enumerable<string> | string | null
    lt?: string
    lte?: string
    gt?: string
    gte?: string
    contains?: string
    startsWith?: string
    endsWith?: string
    not?: NestedStringNullableFilter | string | null
  }

  export type NestedIntNullableFilter = {
    equals?: number | null
    in?: Enumerable<number> | number | null
    notIn?: Enumerable<number> | number | null
    lt?: number
    lte?: number
    gt?: number
    gte?: number
    not?: NestedIntNullableFilter | number | null
  }

  export type NestedBoolNullableFilter = {
    equals?: boolean | null
    not?: NestedBoolNullableFilter | boolean | null
  }

  export type NestedIntFilter = {
    equals?: number
    in?: Enumerable<number> | number
    notIn?: Enumerable<number> | number
    lt?: number
    lte?: number
    gt?: number
    gte?: number
    not?: NestedIntFilter | number
  }

  export type NestedStringWithAggregatesFilter = {
    equals?: string
    in?: Enumerable<string> | string
    notIn?: Enumerable<string> | string
    lt?: string
    lte?: string
    gt?: string
    gte?: string
    contains?: string
    startsWith?: string
    endsWith?: string
    not?: NestedStringWithAggregatesFilter | string
    _count?: NestedIntFilter
    _min?: NestedStringFilter
    _max?: NestedStringFilter
  }

  export type NestedStringNullableWithAggregatesFilter = {
    equals?: string | null
    in?: Enumerable<string> | string | null
    notIn?: Enumerable<string> | string | null
    lt?: string
    lte?: string
    gt?: string
    gte?: string
    contains?: string
    startsWith?: string
    endsWith?: string
    not?: NestedStringNullableWithAggregatesFilter | string | null
    _count?: NestedIntNullableFilter
    _min?: NestedStringNullableFilter
    _max?: NestedStringNullableFilter
  }

  export type NestedIntNullableWithAggregatesFilter = {
    equals?: number | null
    in?: Enumerable<number> | number | null
    notIn?: Enumerable<number> | number | null
    lt?: number
    lte?: number
    gt?: number
    gte?: number
    not?: NestedIntNullableWithAggregatesFilter | number | null
    _count?: NestedIntNullableFilter
    _avg?: NestedFloatNullableFilter
    _sum?: NestedIntNullableFilter
    _min?: NestedIntNullableFilter
    _max?: NestedIntNullableFilter
  }

  export type NestedFloatNullableFilter = {
    equals?: number | null
    in?: Enumerable<number> | number | null
    notIn?: Enumerable<number> | number | null
    lt?: number
    lte?: number
    gt?: number
    gte?: number
    not?: NestedFloatNullableFilter | number | null
  }

  export type NestedBoolNullableWithAggregatesFilter = {
    equals?: boolean | null
    not?: NestedBoolNullableWithAggregatesFilter | boolean | null
    _count?: NestedIntNullableFilter
    _min?: NestedBoolNullableFilter
    _max?: NestedBoolNullableFilter
  }

  export type NestedIntWithAggregatesFilter = {
    equals?: number
    in?: Enumerable<number> | number
    notIn?: Enumerable<number> | number
    lt?: number
    lte?: number
    gt?: number
    gte?: number
    not?: NestedIntWithAggregatesFilter | number
    _count?: NestedIntFilter
    _avg?: NestedFloatFilter
    _sum?: NestedIntFilter
    _min?: NestedIntFilter
    _max?: NestedIntFilter
  }

  export type NestedFloatFilter = {
    equals?: number
    in?: Enumerable<number> | number
    notIn?: Enumerable<number> | number
    lt?: number
    lte?: number
    gt?: number
    gte?: number
    not?: NestedFloatFilter | number
  }

  export type DVaultCreateWithoutNoteInput = {
    name?: string | null
    fsPath: string
    workspace: WorkspaceCreateNestedOneWithoutVaultsInput
  }

  export type DVaultUncheckedCreateWithoutNoteInput = {
    id?: number
    name?: string | null
    fsPath: string
    wsRoot: string
  }

  export type DVaultCreateOrConnectWithoutNoteInput = {
    where: DVaultWhereUniqueInput
    create: XOR<DVaultCreateWithoutNoteInput, DVaultUncheckedCreateWithoutNoteInput>
  }

  export type DVaultUpsertWithoutNoteInput = {
    update: XOR<DVaultUpdateWithoutNoteInput, DVaultUncheckedUpdateWithoutNoteInput>
    create: XOR<DVaultCreateWithoutNoteInput, DVaultUncheckedCreateWithoutNoteInput>
  }

  export type DVaultUpdateWithoutNoteInput = {
    name?: NullableStringFieldUpdateOperationsInput | string | null
    fsPath?: StringFieldUpdateOperationsInput | string
    workspace?: WorkspaceUpdateOneRequiredWithoutVaultsNestedInput
  }

  export type DVaultUncheckedUpdateWithoutNoteInput = {
    id?: IntFieldUpdateOperationsInput | number
    name?: NullableStringFieldUpdateOperationsInput | string | null
    fsPath?: StringFieldUpdateOperationsInput | string
    wsRoot?: StringFieldUpdateOperationsInput | string
  }

  export type WorkspaceCreateWithoutVaultsInput = {
    wsRoot: string
    prismaSchemaVersion: number
  }

  export type WorkspaceUncheckedCreateWithoutVaultsInput = {
    wsRoot: string
    prismaSchemaVersion: number
  }

  export type WorkspaceCreateOrConnectWithoutVaultsInput = {
    where: WorkspaceWhereUniqueInput
    create: XOR<WorkspaceCreateWithoutVaultsInput, WorkspaceUncheckedCreateWithoutVaultsInput>
  }

  export type NoteCreateWithoutVaultInput = {
    id: string
    fname?: string | null
    title?: string | null
    updated?: number | null
    created?: number | null
    stub?: boolean | null
  }

  export type NoteUncheckedCreateWithoutVaultInput = {
    id: string
    fname?: string | null
    title?: string | null
    updated?: number | null
    created?: number | null
    stub?: boolean | null
  }

  export type NoteCreateOrConnectWithoutVaultInput = {
    where: NoteWhereUniqueInput
    create: XOR<NoteCreateWithoutVaultInput, NoteUncheckedCreateWithoutVaultInput>
  }

  export type WorkspaceUpsertWithoutVaultsInput = {
    update: XOR<WorkspaceUpdateWithoutVaultsInput, WorkspaceUncheckedUpdateWithoutVaultsInput>
    create: XOR<WorkspaceCreateWithoutVaultsInput, WorkspaceUncheckedCreateWithoutVaultsInput>
  }

  export type WorkspaceUpdateWithoutVaultsInput = {
    wsRoot?: StringFieldUpdateOperationsInput | string
    prismaSchemaVersion?: IntFieldUpdateOperationsInput | number
  }

  export type WorkspaceUncheckedUpdateWithoutVaultsInput = {
    wsRoot?: StringFieldUpdateOperationsInput | string
    prismaSchemaVersion?: IntFieldUpdateOperationsInput | number
  }

  export type NoteUpsertWithWhereUniqueWithoutVaultInput = {
    where: NoteWhereUniqueInput
    update: XOR<NoteUpdateWithoutVaultInput, NoteUncheckedUpdateWithoutVaultInput>
    create: XOR<NoteCreateWithoutVaultInput, NoteUncheckedCreateWithoutVaultInput>
  }

  export type NoteUpdateWithWhereUniqueWithoutVaultInput = {
    where: NoteWhereUniqueInput
    data: XOR<NoteUpdateWithoutVaultInput, NoteUncheckedUpdateWithoutVaultInput>
  }

  export type NoteUpdateManyWithWhereWithoutVaultInput = {
    where: NoteScalarWhereInput
    data: XOR<NoteUpdateManyMutationInput, NoteUncheckedUpdateManyWithoutNoteInput>
  }

  export type NoteScalarWhereInput = {
    AND?: Enumerable<NoteScalarWhereInput>
    OR?: Enumerable<NoteScalarWhereInput>
    NOT?: Enumerable<NoteScalarWhereInput>
    id?: StringFilter | string
    fname?: StringNullableFilter | string | null
    title?: StringNullableFilter | string | null
    updated?: IntNullableFilter | number | null
    created?: IntNullableFilter | number | null
    stub?: BoolNullableFilter | boolean | null
    dVaultId?: IntFilter | number
  }

  export type DVaultCreateWithoutWorkspaceInput = {
    name?: string | null
    fsPath: string
    Note?: NoteCreateNestedManyWithoutVaultInput
  }

  export type DVaultUncheckedCreateWithoutWorkspaceInput = {
    id?: number
    name?: string | null
    fsPath: string
    Note?: NoteUncheckedCreateNestedManyWithoutVaultInput
  }

  export type DVaultCreateOrConnectWithoutWorkspaceInput = {
    where: DVaultWhereUniqueInput
    create: XOR<DVaultCreateWithoutWorkspaceInput, DVaultUncheckedCreateWithoutWorkspaceInput>
  }

  export type DVaultUpsertWithWhereUniqueWithoutWorkspaceInput = {
    where: DVaultWhereUniqueInput
    update: XOR<DVaultUpdateWithoutWorkspaceInput, DVaultUncheckedUpdateWithoutWorkspaceInput>
    create: XOR<DVaultCreateWithoutWorkspaceInput, DVaultUncheckedCreateWithoutWorkspaceInput>
  }

  export type DVaultUpdateWithWhereUniqueWithoutWorkspaceInput = {
    where: DVaultWhereUniqueInput
    data: XOR<DVaultUpdateWithoutWorkspaceInput, DVaultUncheckedUpdateWithoutWorkspaceInput>
  }

  export type DVaultUpdateManyWithWhereWithoutWorkspaceInput = {
    where: DVaultScalarWhereInput
    data: XOR<DVaultUpdateManyMutationInput, DVaultUncheckedUpdateManyWithoutVaultsInput>
  }

  export type DVaultScalarWhereInput = {
    AND?: Enumerable<DVaultScalarWhereInput>
    OR?: Enumerable<DVaultScalarWhereInput>
    NOT?: Enumerable<DVaultScalarWhereInput>
    id?: IntFilter | number
    name?: StringNullableFilter | string | null
    fsPath?: StringFilter | string
    wsRoot?: StringFilter | string
  }

  export type NoteUpdateWithoutVaultInput = {
    id?: StringFieldUpdateOperationsInput | string
    fname?: NullableStringFieldUpdateOperationsInput | string | null
    title?: NullableStringFieldUpdateOperationsInput | string | null
    updated?: NullableIntFieldUpdateOperationsInput | number | null
    created?: NullableIntFieldUpdateOperationsInput | number | null
    stub?: NullableBoolFieldUpdateOperationsInput | boolean | null
  }

  export type NoteUncheckedUpdateWithoutVaultInput = {
    id?: StringFieldUpdateOperationsInput | string
    fname?: NullableStringFieldUpdateOperationsInput | string | null
    title?: NullableStringFieldUpdateOperationsInput | string | null
    updated?: NullableIntFieldUpdateOperationsInput | number | null
    created?: NullableIntFieldUpdateOperationsInput | number | null
    stub?: NullableBoolFieldUpdateOperationsInput | boolean | null
  }

  export type NoteUncheckedUpdateManyWithoutNoteInput = {
    id?: StringFieldUpdateOperationsInput | string
    fname?: NullableStringFieldUpdateOperationsInput | string | null
    title?: NullableStringFieldUpdateOperationsInput | string | null
    updated?: NullableIntFieldUpdateOperationsInput | number | null
    created?: NullableIntFieldUpdateOperationsInput | number | null
    stub?: NullableBoolFieldUpdateOperationsInput | boolean | null
  }

  export type DVaultUpdateWithoutWorkspaceInput = {
    name?: NullableStringFieldUpdateOperationsInput | string | null
    fsPath?: StringFieldUpdateOperationsInput | string
    Note?: NoteUpdateManyWithoutVaultNestedInput
  }

  export type DVaultUncheckedUpdateWithoutWorkspaceInput = {
    id?: IntFieldUpdateOperationsInput | number
    name?: NullableStringFieldUpdateOperationsInput | string | null
    fsPath?: StringFieldUpdateOperationsInput | string
    Note?: NoteUncheckedUpdateManyWithoutVaultNestedInput
  }

  export type DVaultUncheckedUpdateManyWithoutVaultsInput = {
    id?: IntFieldUpdateOperationsInput | number
    name?: NullableStringFieldUpdateOperationsInput | string | null
    fsPath?: StringFieldUpdateOperationsInput | string
  }



  /**
   * Batch Payload for updateMany & deleteMany & createMany
   */

  export type BatchPayload = {
    count: number
  }

  /**
   * DMMF
   */
  export const dmmf: runtime.BaseDMMF
}